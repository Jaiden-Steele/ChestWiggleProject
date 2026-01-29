class StateMsg:
    def __init__(self, state):
        self.state = state

    def to_dict(self):
        return self.__dict__