import time
import locale
import datetime
from report import report_sxw
import time
import pooler
import rml_parse

class year_salary_report(rml_parse.rml_parse):

    def __init__(self, cr, uid, name, context):
        super(year_salary_report, self).__init__(cr, uid, name, context)
        self.localcontext.update({
            'time': time,
            'get_employee' : self.get_employee,
            'get_periods'  : self.get_periods,
            'get_months_tol' : self.get_months_tol,
            'get_total' : self.get_total,
        })

        self.mnths =[]
        self.mnths_tol = []
        self.total=0.0

    def get_periods(self,form):
#       Get start year-month-date and end year-month-date
        fy = int(form['date_from'][0:4])
        ly = int(form['date_to'][0:4])

        fm = int(form['date_from'][5:7])
        lm = int(form['date_to'][5:7])
        no_months = (ly-fy)*12+lm-fm + 1
        cm = fm
        cy = fy

#       Get name of the months from integer
        mnth_name = []
        for count in range(0,no_months):
            m = datetime.date(cy, cm, 1).strftime('%b')
            mnth_name.append(m)
            self.mnths.append(str(cm)+'-'+str(cy))
            if cm == 12:
                cm = 0
                cy = ly
            cm = cm +1
        return [mnth_name]

    def get_employee(self,form):
        ls1=[]
        ls = []
        periods = []
        tol_mnths=['Total',0,0,0,0,0,0,0,0,0,0,0,0]
        emp = pooler.get_pool(self.cr.dbname).get('hr.employee')
        emp_ids = form['employee_ids']
        empll  = emp.browse(self.cr,self.uid, emp_ids)
        cnt = 1
        for emp_id in empll:
            ls1.append(emp_id.name)
            tol = 0.0
            for mnth in self.mnths:
                if len(mnth) != 7:
                    mnth = '0' + str(mnth)
                query = "select net from hr_payslip where employee_id = "+str(emp_id.id)+" and to_char(date,'mm-yyyy') like '%"+mnth+"%' and state = 'done' "
                self.cr.execute(query)
                sal = self.cr.fetchall()
                try:
                    ls1.append(sal[0][0])
                except:
                    ls1.append(0)
                try:
                    tol += sal[0][0]
                    tol_mnths[cnt] = tol_mnths[cnt] + sal[0][0]
                except:
                    tol += 0
                cnt = cnt + 1
            cnt = 1
            ls1.append(tol)
            ls.append(ls1)
            ls1 = []
        self.mnths_tol.append(tol_mnths)
        return ls

    def get_months_tol(self):
        return self.mnths_tol

    def get_total(self):
        for item in self.mnths_tol:
            for count in range(1,len(item)):
              self.total += item[count]
        return self.total

report_sxw.report_sxw('report.year.salary', 'hr.payslip', 'hr_payroll/report/report_year_report.rml', parser=year_salary_report,header='internal landscape')



