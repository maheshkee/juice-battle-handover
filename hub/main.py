"""
main.py - Juice Battle orchestrator.
Owns zero logic. Wires modules only.
Orchestrator law: if there is a conditional, a calculation, or a threshold here,
it is in the wrong file.
"""

import sys
import os
import atexit
import signal
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(message)s',
    stream=sys.stderr,
)

# ensure hub/ modules resolve correctly regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from storage   import Storage
from transport import Transport
from game      import Game
from dashboard import Dashboard
from ambient   import AmbientPlayer


def main():
    import subprocess
    subprocess.run(['touch', '/tmp/jb_reload'], check=False)
    # instantiate modules - each receives its dependencies via constructor
    storage   = Storage(config.DB_PATH)

    def _on_clean_exit():
        """
        Called only on clean shutdown (SIGTERM from systemctl stop/restart).
        Writes a flag so the next startup knows to reset scores.
        WHY: atexit fires on sys.exit() but NOT on SIGKILL or power loss.
        This is exactly the distinction we need:
          clean restart  → flag written → scores reset on next start
          crash/power loss → flag never written → scores resume on next start
        """
        try:
            storage.set_kv('service_stopped_cleanly', 'true')
            logging.info("Clean shutdown — scores will reset on next start")
        except Exception as e:
            logging.warning("Could not write shutdown flag: %s", e)

    atexit.register(_on_clean_exit)
    # SIGTERM (sent by systemctl stop/restart) does not trigger atexit by default.
    # Convert it to sys.exit(0) so atexit fires.
    # SIGKILL and power loss bypass this entirely — that's the correct behaviour.
    signal.signal(signal.SIGTERM, lambda sig, frame: sys.exit(0))
    transport = Transport()
    game_inst = Game(storage)
    ambient   = AmbientPlayer()
    dashboard = Dashboard(game_inst, ambient=ambient)

    # wire ambient player into game for round announcements
    game_inst.set_ambient(ambient)

    # wire: transport delivers POUR_SETTLED events to game
    # game does NOT self-register - orchestrator law
    transport.on_event(game_inst.on_pour_settled,      msg_filter='POUR_SETTLED')
    transport.on_event(game_inst.on_pour_active,       msg_filter='POUR_ACTIVE')
    transport.on_event(game_inst.on_node_disconnected, msg_filter='NODE_DISCONNECTED')
    transport.on_event(game_inst.on_node_connected,    msg_filter='NODE_CONNECTED')

    # start in dependency order
    game_inst.start(node_count=2)   # dual node - S013
    transport.start()               # begins TCP connection to ble_scanner service
    ambient.start()                 # background music + announcement scheduler
    dashboard.start()               # blocks - runs Flask-SocketIO server


if __name__ == '__main__':
    main()
