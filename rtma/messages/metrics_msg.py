class MetricsMsg:
    def __init__(self, snr_db):
        self.snr_db = snr_db

    def to_dict(self):
        return self.__dict__
