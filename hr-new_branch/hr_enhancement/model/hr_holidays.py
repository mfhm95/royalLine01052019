# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import math
import datetime
from datetime import timedelta


class LeaveTypes(models.Model):
    _inherit = 'hr.holidays.status'
    
    unpaid = fields.Boolean('Leave Without Paid')
    name = fields.Char('Name', required=True)
    
    @api.multi
    def name_get(self):
        if not self._context.get('employee_id'):
            # leave counts is based on employee_id, would be inaccurate if not based on correct employee
            return super(LeaveTypes, self).name_get()
        res = []
        for record in self:
            name = record.name
            if not record.limit:
                leav_t =  record.leaves_taken
                max_leav = record.max_leaves
                name = str(name) +'(' +str(leav_t) +'/'+str(max_leav) +')'
                
#                 name = "%(name)s (%(count)s)" % {
#                     'name': name,
#                     'count': _('%g remaining out of %g') % (record.virtual_remaining_leaves or 0.0, record.max_leaves or 0.0)
#                 }
            res.append((record.id, name))
        return res
    
class HRHolidays(models.Model):
    _inherit = "hr.holidays"
    
    public_id = fields.Many2one('hr.public_holiday') 
    
    def _get_schedule_holidays(self, date_from, date_to, employee_id):
        day_of_week = {'Monday':0 ,'Tuesday':1 ,'Wednesday':2 ,'Thursday':3 ,'Friday':4 ,'Saturday':5 ,'Sunday':6 }
        employee = self.env['hr.employee'].browse(employee_id)
        contract = employee.contract_id
        holidays_days = 0
        if contract:
            if contract and contract.resource_calendar_id:
                working_days = []
                for day in contract.resource_calendar_id.attendance_ids:
                    working_days.append(int(day.dayofweek))
                    
                    
                DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
                from_dt = datetime.datetime.strptime(date_from, DATETIME_FORMAT).date()
                to_dt = datetime.datetime.strptime(date_to, DATETIME_FORMAT).date()
                delta = to_dt - from_dt
                for i in range(delta.days + 1):
                    date = from_dt + timedelta(days=i)
                    if day_of_week[date.strftime('%A')] not in working_days:
                        holidays_days += 1
                    else:
                        off_day = self.official_leave(employee, date)
                        if off_day:
                            holidays_days += 1
                    
        return holidays_days
    
    
    
    def official_leave(self, employee, datetime_day):
        res = False
        contract = employee.contract_id
        if contract and contract.resource_calendar_id:
            day = datetime_day.strftime("%Y-%m-%d")
            holiday_ids = self.env['resource.calendar.leaves'].search([('calendar_id','=',contract.resource_calendar_id.id),
                                                                                     ('resource_id','=',employee.id),
                                                                                     ('date_from','<=',day),
                                                                                     ('date_to','>=',day)])
            if not holiday_ids:
                holiday_ids = self.env['resource.calendar.leaves'].search([('calendar_id','=',contract.resource_calendar_id.id),
                                                                                         ('resource_id','=',False),
                                                                                         ('date_from','<=',day),
                                                                                         ('date_to','>=',day)])
            if holiday_ids:
                res = 'new day'
        return res
    
    
    
    def _get_number_of_days(self, date_from, date_to, employee_id):
        schedul_off_days = self._get_schedule_holidays(date_from, date_to, employee_id)
        DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
        from_dt = datetime.datetime.strptime(date_from, DATETIME_FORMAT)
        to_dt = datetime.datetime.strptime(date_to, DATETIME_FORMAT)
        employee = self.env['hr.employee'].browse(employee_id)
        work_hour = employee.work_hour
        timedelta = to_dt - from_dt
        if work_hour:
            work_time_second = 60*60*work_hour
        else:
            work_time_second = 86400 # 60*60*24
            
        dd = float(timedelta.seconds) / work_time_second
        if timedelta.days:
            if (float(timedelta.seconds) / work_time_second) > 1:
                diff_day = timedelta.days + 1
            else:
                diff_day = timedelta.days + float(timedelta.seconds) / work_time_second
        else:
            diff_day = float(timedelta.seconds) / work_time_second
            if diff_day >1 :
                diff_day = 1
        
        public_holidays = self.get_special_days(date_from, date_to, employee_id)
        
        return diff_day-schedul_off_days-public_holidays
            
            
    def get_special_days(self, date_from, date_to, employee_id):
        employee = self.env['hr.employee'].browse(employee_id)
        DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
        public_leaves = self.env['hr.public_holiday'].search([('state','=','done'),('date', '<=', date_to),('date_to', '>=', date_from),])
        special_days = 0
        if employee.work_hour:
            work_time_second = 60*60*employee.work_hour
        else:
            work_time_second = 86400 # 60*60*24
        # for each date in the selected period, check if a public holiday exists
        if public_leaves:
            leave_date_from = datetime.datetime.strptime(date_from,DATETIME_FORMAT)
            leave_date_to = datetime.datetime.strptime(date_to,DATETIME_FORMAT)
            
            for pub in public_leaves:
                if employee_id in public_leaves.employee_ids.mapped('id'):
                    pub_date_from = datetime.datetime.strptime(pub.date,DATETIME_FORMAT)
                    pub_date_to = datetime.datetime.strptime(pub.date_to,DATETIME_FORMAT)
                    if date_from >= pub.date:
                        special_days += abs((pub_date_to-leave_date_from).days) + (float((pub_date_to-leave_date_from).seconds) / work_time_second)
                    elif date_to <= pub.date_to:
                        special_days += abs((leave_date_to-pub_date_from).days) + (float((leave_date_to-pub_date_from).seconds) / work_time_second)
                    else:
                        special_days += abs((pub_date_to-pub_date_from).days) + (float((pub_date_to-pub_date_from).seconds) / work_time_second)
            
        return special_days