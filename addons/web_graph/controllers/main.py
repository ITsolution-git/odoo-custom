from base.controllers.main import View
import base.common as openerpweb

class GraphView(View):
    _cp_path = "/base_graph/graphview"

    @openerpweb.jsonrequest
    def load(self, req, model, view_id):
        fields_view = self.fields_view_get(req, model, view_id, 'graph')
        all_fields = req.session.model(model).fields_get()
        return {'fields_view': fields_view, 'all_fields':all_fields}
