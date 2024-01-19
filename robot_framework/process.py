"""This module contains the main process of the robot."""

import os

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from itk_dev_shared_components.sap import multi_session

from robot_framework.sap import zdkd_list_sbs_aftale, ryk_afklar


def process(orchestrator_connection: OrchestratorConnection) -> None:
    """Do the primary process of the robot."""
    orchestrator_connection.log_trace("Running process.")

    session = multi_session.spawn_sessions(1)[0]

    zdkd_list_sbs_aftale.search_fp_list(session)
    num_cases = ryk_afklar.search_work_list(session)

    for i in range(num_cases):
        ryk_afklar.handle_case(orchestrator_connection, session, i)


if __name__ == '__main__':
    conn_string = os.getenv("OpenOrchestratorConnString")
    crypto_key = os.getenv("OpenOrchestratorKey")
    oc = OrchestratorConnection("Sletning Test", conn_string, crypto_key, "")
    process(oc)
