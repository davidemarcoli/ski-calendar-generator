from datetime import datetime
import hashlib
import json
from pathlib import Path

import pytz


class EventStateTracker:
    def __init__(self, cache_dir: Path):
        self.state_file = cache_dir / "event_states.json"
        if not self.state_file.exists():
            self.state_file.write_text(json.dumps({}))
        
        with open(self.state_file, 'r') as f:
            self.states = json.load(f)
    
    def compute_event_hash(self, race, run, comp, details):
        """Compute a hash of the event data to detect changes."""
        event_data = {
            'race_id': race['race_id'],
            'run_number': run.get('number', 1),
            'date': race['date'],
            'time': run.get('time'),
            'status': run.get('status'),
            'info': run.get('info'),
            'location': comp['location'],
            'discipline': race['discipline'],
            'gender': comp['gender']
        }
        return hashlib.sha256(json.dumps(event_data, sort_keys=True).encode()).hexdigest()
    
    def get_event_state(self, event_id: str) -> dict:
        """Get the current state for an event, initialize if not exists."""
        if event_id not in self.states:
            self.states[event_id] = {
                'sequence': -1,
                'created': datetime.now(pytz.UTC).isoformat(),
                'hash': None
            }
        return self.states[event_id]
    
    def update_event_state(self, event_id: str, event_hash: str) -> int:
        """Update event state and return sequence number."""
        state = self.get_event_state(event_id)
        
        if state['hash'] != event_hash:
            # Event has changed, increment sequence
            state['sequence'] += 1
            state['hash'] = event_hash
            # Save states
            with open(self.state_file, 'w') as f:
                json.dump(self.states, f, indent=2)
        
        return state['sequence']