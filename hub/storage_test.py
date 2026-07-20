import sys
import os
import time
import sqlite3
import logging
from datetime import datetime

# WHY: add hub/ to path so imports work when run from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from transport import Transport
from storage import Storage
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S"
)

storage = Storage("hub/data/jb.db")

session_id = storage.open_session(node_count=1)
print(f"Test session opened: id={session_id}")


def on_event(event):
    msg = event.get('msg')
    if msg == 'DIAG':
        storage.record_health(
            ts=event.get('ts', datetime.utcnow().isoformat()),
            node_id=event.get('node', -1),
            msg='DIAG',
            current_g=event.get('current_g'),
            slope_gs=event.get('slope_gs'),
            state=event.get('state'),
            quality=event.get('quality'),
        )
        print(f"  [health] DIAG node={event.get('node')} "
              f"state={event.get('state')} quality={event.get('quality')}")
    elif msg == 'HEARTBEAT':
        storage.record_health(
            ts=event.get('ts', datetime.utcnow().isoformat()),
            node_id=event.get('node', -1),
            msg='HEARTBEAT',
            sigma_g=event.get('sigma_g'),
            seq=event.get('seq'),
        )
    elif msg == 'POUR_SETTLED':
        storage.record_pour(
            session_id=session_id,
            ts=event.get('ts', datetime.utcnow().isoformat()),
            node_id=event.get('node', -1),
            delta_g=event.get('delta_g', 0.0),
            sigma_g=event.get('sigma_g', 0.0),
            seq=event.get('seq', 0),
        )
        print(f"  [pour] node={event.get('node')} delta={event.get('delta_g')}g")


transport = Transport()
transport.on_event(on_event)
transport.start()

print("Running for 30s - pour something if you can...")
time.sleep(30)

transport.stop()
storage.close_session(session_id)

conn = sqlite3.connect("hub/data/jb.db")
for table in ['sessions', 'pour_events', 'node_health', 'error_log']:
    count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    print(f"  {table}: {count} rows")
conn.close()
