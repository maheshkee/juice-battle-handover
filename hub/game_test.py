import sys
import time
import logging
import sqlite3
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config
from storage import Storage
from transport import Transport
from game import Game

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("game_test")

DB_PATH  = Path(__file__).parent / "data" / "jb.db"
RUN_SECS = 60


def main():
    log.info("=== game_test.py - %ds window ===", RUN_SECS)
    log.info("Pour one glass (>=%.0fg) during this window", config.GLASS_VOLUME_G)
    log.info("Config: POUR_WINDOW_S=%.1fs  POUR_SIGMA_K=%.1f  POUR_MIN_G=%.1fg",
             config.POUR_WINDOW_S, config.POUR_SIGMA_K, config.POUR_MIN_G)

    storage   = Storage(str(DB_PATH))
    transport = Transport()
    game      = Game(storage)

    # main.py wiring pattern - Game does not self-register
    transport.on_event(game.on_pour_settled, msg_filter="POUR_SETTLED")

    game.start(node_count=1)
    transport.start()

    log.info("Running - pour now ...")
    time.sleep(RUN_SECS)

    transport.stop()
    game.stop()

    # --- Results ---
    state = game.get_state()
    log.info("=== Final state ===")
    log.info("  session_id  : %s", state["session_id"])
    log.info("  glass_count : %s", state["glass_count"])
    log.info("  partial_g   : %s", state["partial_g"])

    conn = sqlite3.connect(str(DB_PATH))
    pour_rows = conn.execute(
        "SELECT COUNT(*) FROM pour_events WHERE session_id=?",
        (state["session_id"],)
    ).fetchone()[0]
    sess_row = conn.execute(
        "SELECT * FROM sessions WHERE id=?",
        (state["session_id"],)
    ).fetchone()
    conn.close()

    log.info("  pour_events rows : %d", pour_rows)
    log.info("  session row      : %s", sess_row)

    # --- Success criteria ---
    print("\n--- SUCCESS CRITERIA ---")
    poured_glass = state["glass_count"].get(0, 0) >= 1
    criteria = [
        ("No crashes during 60s run",            True),
        ("glass_count[0] >= 1 after real pour",  poured_glass),
        ("pour_events rows > 0",                 pour_rows > 0),
        ("session_id is not None",               state["session_id"] is not None),
    ]
    all_pass = True
    for label, result in criteria:
        status = "PASS" if result else "FAIL"
        if not result:
            all_pass = False
        print(f"  [{status}] {label}")

    print(f"\n{'ALL PASS' if all_pass else 'SOME FAILED'}")
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
