from datetime import datetime
import logging
import icalendar
import json
import pytz

from ski_calendar_generator.ski_data_fetcher import SkiDataFetcher

logger = logging.getLogger(__name__)

class CalendarGenerator:
    def __init__(self):
        self.fetcher = SkiDataFetcher()
    
    def generate_ical(self) -> bytes:
        """Generate iCal file from cached competition data."""
        cal = icalendar.Calendar()
        cal.add('prodid', '-//FIS Ski Calendar//EN')
        cal.add('version', '2.0')
        
        # Load cached data
        with open(self.fetcher.competitions_cache_file, 'r') as f:
            competitions = json.load(f)
        
        with open(self.fetcher.details_cache_file, 'r') as f:
            details_cache = json.load(f)
        
        for comp in competitions:
            event_id = comp['event_id']
            if event_id not in details_cache:
                continue
            
            details = details_cache[event_id]
            
            # Create events for each race in the competition
            for race in details['races']:
                if race['is_training']:
                    continue  # Skip training runs
                
                # Get base start time from race date
                base_start_time = datetime.fromisoformat(race['date']) if "T" in race['date'] else datetime.combine(
                    datetime.strptime(race['date'], '%Y-%m-%d').date(),
                    datetime.strptime('00:00:00', '%H:%M:%S').time()
                )

                # Create an event for each run
                runs = race['runs'] if race['runs'] else [{'number': 1, 'time': None}]
                for run in runs:
                    event = icalendar.Event()
                    
                    # Start time handling for this specific run
                    start_time = base_start_time
                    if run.get('time'):
                        try:
                            time_str = run['time']
                            if time_str and ':' in time_str:
                                hour, minute = map(int, time_str.split(':')[:2])
                                start_time = start_time.replace(hour=hour, minute=minute)
                        except (ValueError, IndexError):
                            logger.warning(f"Could not parse time string: {time_str} for race {race['race_id']} run {run.get('number', 'unknown')}")
                    
                    # Set timezone to UTC
                    start_time = pytz.utc.localize(start_time)
                    
                    # Create event summary with run number
                    run_number = run.get('number', 1)
                    summary = f"{comp['location']} - {race['discipline']} Run {run_number} ({comp['gender']})"
                    
                    # Add run status and info if available
                    description = f"Run {run_number}\n"
                    if run.get('status'):
                        description += f"Status: {run['status']}\n"
                    if run.get('info'):
                        description += f"Info: {run['info']}\n"

                    broadcasters = details.get('broadcasters', [])
                    if broadcasters:
                        description += "\nBroadcasters:\n"
                        
                        for broadcaster in broadcasters:
                            description += f"- {broadcaster['name']} ({', '.join(broadcaster['countries'])})\n"
                            if broadcaster['url']:
                                description += f"  {broadcaster['url']}\n"
                    
                    event.add('summary', summary)
                    event.add('dtstart', start_time)
                    event.add('dtend', start_time.replace(hour=start_time.hour + 2))  # Assume 2 hours per run
                    event.add('location', f"{comp['location']}, {comp['country']}")
                    event.add('description', description)
                    
                    # Add unique identifier including run number
                    event.add('uid', f"{race['race_id']}-run{run_number}@fis-ski.com")
                    
                    cal.add_component(event)
        
        return cal.to_ical()