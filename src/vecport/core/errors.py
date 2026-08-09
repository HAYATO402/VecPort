class VecPortError(Exception):
    pass


class ConnectionError(VecPortError):
    pass


class CollectionNotFoundError(VecPortError):
    pass


class UnsupportedFeatureError(VecPortError):
    pass