
def fixQnameOfUriWithTrailingSlash():
    import rdflib.namespace
    old_split = rdflib.namespace.split_uri
    def new_split(uri):
        try:
            return old_split(uri)
        except Exception:
            return uri, ''
    rdflib.namespace.split_uri = new_split
