from abc import ABC, abstractmethod
from driver.display.display import Display


class BaseApplication(ABC):
    """
    Base Class für alle Applications.
    Definiert eine einheitliche Schnittstelle für alle Features.
    """

    def __init__(self, display: Display = None, db_key: str = None):
        """
        Initialisiert die Base Application.

        Args:
            display: Display-Instanz (optional, nutzt Simulation falls nicht gesetzt)
            db_key: Datenbank-Key für diese Applikation (optional)
        """
        self.display = display if display else Display(simulation=True)
        self.db_key = db_key

    @abstractmethod
    def run(self):
        """
        Hauptmethode für die Ausführung der Applikation.
        Muss von jeder abgeleiteten Klasse implementiert werden.
        """
        pass
