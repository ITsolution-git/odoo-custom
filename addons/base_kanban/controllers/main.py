import base.common as openerpweb

from base.controllers.main import View

class KanbanView(View):
    _cp_path = "/base_kanban/kanbanview"

    @openerpweb.jsonrequest
    def load(self, req, model, view_id):
        fields_view = self.fields_view_get(req, model, view_id, 'kanban')
        return {'fields_view': fields_view}
