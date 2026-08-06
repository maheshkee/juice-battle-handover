"""
main.py - Juice Battle orchestrator.
Owns zero logic. Wires modules only.
Orchestrator law: if there is a conditional, a calculation, or a threshold here,
it is in the wrong file.
"""

import sys
import os
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
    # instantiate modules - each receives its dependencies via constructor
    storage   = Storage(config.DB_PATH)
    transport = Transport()
    game_inst = Game(storage)
    dashboard = Dashboard(game_inst)
    ambient   = AmbientPlayer()

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
