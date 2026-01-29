class FilteredAccelMsg:
    """
    Filtered acceleration sample (post digital filtering)
    """
    def __init__(self, t, value):
        self.t = t              # time in seconds
        self.value = value      # filtered acceleration (g or m/s^2)

    def to_dict(self):
        return {
            "t": self.t,
            "value": self.value
        }
