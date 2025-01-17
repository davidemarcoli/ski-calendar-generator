from datetime import datetime
import logging
import icalendar
import json
import pytz

from ski_calendar_generator.event_state_tracker import EventStateTracker
from ski_calendar_generator.ski_data_fetcher import SkiDataFetcher

logger = logging.getLogger(__name__)

class CalendarGenerator:
    def __init__(self):
        self.fetcher = SkiDataFetcher()
        self.last_data = None
    
    def generate_ical(self) -> bytes:
        """Generate iCal file from cached competition data."""
        cal = icalendar.Calendar()
        cal.add('prodid', '-//FIS Ski Calendar//EN')
        cal.add('version', '2.0')
        cal.add('method', 'PUBLISH')
        cal.add('X-WR-CALNAME', 'FIS Ski Calendar')

        # Initialize event state tracker
        state_tracker = EventStateTracker(self.fetcher.CACHE_DIR)
        
        # Load cached data
        with open(self.fetcher.competitions_cache_file, 'r') as f:
            competitions = json.load(f)
        
        with open(self.fetcher.details_cache_file, 'r') as f:
            details_cache = json.load(f)

        # Get current time in UTC for timestamps
        now = datetime.now(pytz.UTC)
        
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

                    # Generate unique event ID
                    event_uid = f"{race['race_id']}-run{run.get('number', 1)}@fis-ski.com"
                    
                    # Compute event hash and get state
                    event_hash = state_tracker.compute_event_hash(race, run, comp, details)
                    event_state = state_tracker.get_event_state(event_uid)
                    sequence = state_tracker.update_event_state(event_uid, event_hash)
                    
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
                    
                    # Convert MEZ to UTC
                    mez = pytz.timezone('Europe/Zurich')
                    start_time = mez.localize(start_time)
                    start_time = start_time.astimezone(pytz.UTC)
                    
                    # Create event summary with run number
                    run_number = run.get('number', 1) if len(runs) > 1 else None
                    summary = f"{comp['location']} - {race['discipline']}"
                    if run_number:
                        summary += f" Run {run_number}"
                    summary += f" ({comp['gender']})"
                    
                    # Add run status and info if available
                    description = ""
                    if run_number:
                        description += f"Run {run_number}\n"
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
                    event.add('dtend', start_time.replace(hour=start_time.hour + 1))  # Assume 1 hours per run
                    event.add('dtstamp', now)
                    event.add('created', datetime.fromisoformat(event_state['created']))
                    event.add('last-modified', now)
                    event.add('sequence', sequence)
                    event.add('dtstamp', datetime.now())
                    event.add('location', f"{comp['location']}, {comp['country']}")
                    event.add('description', description)
                    event.add('uid', event_uid)
                    
                    cal.add_component(event)
        
        return cal.to_ical()