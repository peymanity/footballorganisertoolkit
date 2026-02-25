Update a Spond match event based on information the user provides (emails, FA Full-Time fixture details, WhatsApp messages, etc).

## Steps

1. First, list upcoming events to find the one to update:

```python
from footballorganisertoolkit.update_helpers import list_upcoming_events, get_event_summary
events = list_upcoming_events()
print(get_event_summary(events))
```

2. From the user's pasted info, extract:
   - Which event this relates to (match by opponent name and/or date)
   - Confirmed kick-off time (if provided)
   - Venue / pitch details (if provided)
   - Any parking, kit, or logistics info for the description
   - Any other relevant details

3. Show the user what you plan to update and get confirmation before proceeding.

4. Apply updates using the helper:

```python
from footballorganisertoolkit.update_helpers import update_event
from datetime import datetime

result = update_event(
    event_id="<matched event ID>",
    heading="<updated heading if time confirmed, remove TBC suffix>",
    start=datetime(2026, M, D, H, M),      # if kick-off time confirmed
    end=datetime(2026, M, D, H, M),         # start + 75 min (single match) or start + 120 min (double header)
    meetup_prior=30,                         # 30 min before kick-off
    description="<updated description>",     # preserve any double header info
    location_query="<venue name, town>",     # will be geocoded automatically
)
```

## Rules

- NEVER include contact details (phone numbers, emails) in the Spond event description
- When confirming kick-off time for an away match, update the heading to remove " - TIME AND DETAILS TBC"
- When kick-off time is confirmed, set end time to start + 75 min for a single match, or start + 120 min (2 hours) for a double header
- Keep the description style consistent with existing events (see examples below)
- Always geocode the location if venue details are updated
- Always show the user a summary of changes and ask for confirmation before updating

## Description style examples

Home match:
```
BLUE (home) kit

Rothamsted venue info: https://drive.google.com/file/d/1Z21E2VEupl3gc1yIs305VgQ9TXECRK70/view?usp=sharing
```

Away match (confirmed details):
```
U13 Division 5
League match

Pitch 6
No dogs allowed on site. If the car park is full it will be closed - please park on the roads marked and not on the grass verges around the school.
EMAP and further info: www.hitchinbelles.com
```

Away match (TBC):
```
Meeting/kickoff time and full details will be confirmed at least 3 days before the match once notified by the home team.
```

Double header (add to end of description):
```
Double header: two matches back to back with 25-minute halves and a 10-20 minute break in between.
```

$ARGUMENTS
