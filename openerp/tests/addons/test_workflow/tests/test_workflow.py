# -*- coding: utf-8 -*-
import openerp
from openerp import SUPERUSER_ID
from openerp.tests import common


class test_workflows(common.TransactionCase):

    def check_activities(self, model_name, i, names):
        """ Check that the record i has workitems in the given activity names.
        """
        instance = self.registry('workflow.instance')
        workitem = self.registry('workflow.workitem')

        # Given the workflow instance associated to the record ...
        instance_id = instance.search(
            self.cr, SUPERUSER_ID,
            [('res_type', '=', model_name), ('res_id', '=', i)])
        self.assertTrue( instance_id, 'A workflow instance is expected.')

        # ... get all its workitems ...
        workitem_ids = workitem.search(
            self.cr, SUPERUSER_ID,
            [('inst_id', '=', instance_id[0])])
        self.assertTrue(
            workitem_ids,
            'The workflow instance should have workitems.')

        # ... and check the activity the are in against the provided names.
        workitem_records = workitem.browse(
            self.cr, SUPERUSER_ID, workitem_ids)
        self.assertEqual(
            sorted([item.act_id.name for item in workitem_records]),
            sorted(names))

    def test_workflow(self):
        model = self.registry('test.workflow.model')
        trigger = self.registry('test.workflow.trigger')

        i = model.create(self.cr, SUPERUSER_ID, {})
        self.check_activities(model._name, i, ['a'])

        # a -> b is just a signal.
        model.signal_workflow(self.cr, SUPERUSER_ID, [i], 'a-b')
        self.check_activities(model._name, i, ['b'])

        # b -> c is a trigger (which is False),
        # so we remain in the b activity.
        model.trigger(self.cr, SUPERUSER_ID, [i])
        self.check_activities(model._name, i, ['b'])

        # b -> c is a trigger (which is set to True).
        # so we go in c when the trigger is called.
        trigger.write(self.cr, SUPERUSER_ID, [1], {'value': True})
        model.trigger(self.cr, SUPERUSER_ID)
        self.check_activities(model._name, i, ['c'])

        self.assertEqual(
            True,
            True)

        model.unlink(self.cr, SUPERUSER_ID, [i])
