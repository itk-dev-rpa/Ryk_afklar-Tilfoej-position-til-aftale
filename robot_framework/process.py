"""This module contains the main process of the robot."""

from OpenOrchestrator.orchestrator_connection.connection import OrchestratorConnection
from itk_dev_shared_components.sap import multi_session
import itk_dev_event_log

from robot_framework.sap import zdkd_list_sbs_aftale, ryk_afklar


def process(orchestrator_connection: OrchestratorConnection) -> None:
    """Do the primary process of the robot."""
    orchestrator_connection.log_trace("Running process.")
    event_log = orchestrator_connection.get_constant("Event Log")
    itk_dev_event_log.setup_logging(event_log.value)

    session = multi_session.spawn_sessions(1)[0]

    zdkd_list_sbs_aftale.search_fp_list(session)
    num_cases = ryk_afklar.search_work_list(session)

    for i in range(num_cases):
        ryk_afklar.handle_case(orchestrator_connection, session, i)
