from cto_tool.settings import USE_REPLICA_DATABASE


class ReplicaRouter:
    def db_for_read(self, model, **hints):
        """
        Reads go to the replica.
        """
        if USE_REPLICA_DATABASE:
            return "replica"
        return None

    def db_for_write(self, model, **hints):
        """
        Writes always go to primary.
        """
        return "default"

    def allow_relation(self, obj1, obj2, **hints):
        """
        Relations between objects are allowed if both objects are
        in the primary/replica pool.
        """
        db_set = {"default", "replica"}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return True
