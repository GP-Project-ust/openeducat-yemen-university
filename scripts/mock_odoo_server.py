#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mock_odoo_server.py — خادم Odoo XML-RPC وهمي للاختبار المحلي الآمن.

يحاكي واجهة /xmlrpc/2 (authenticate + execute_kw) بنماذج OpenEduCat 17
Community كما هي في المستودع الرسمي، حتى تختبر مولّد البيانات دون لمس
قاعدة حقيقية. للتطوير والاختبار فقط.
"""
import re
import sys
import threading
from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler

F = {
    'char': {'type': 'char'}, 'text': {'type': 'text'},
    'integer': {'type': 'integer'}, 'float': {'type': 'float'},
    'boolean': {'type': 'boolean'}, 'date': {'type': 'date'},
    'datetime': {'type': 'datetime'}, 'selection': {'type': 'selection'},
    'many2one': {'type': 'many2one'}, 'many2many': {'type': 'many2many'},
    'one2many': {'type': 'one2many'},
}


def fields(**kw):
    out = {}
    for name, ftype in kw.items():
        out[name] = dict(F[ftype])
        if name in ('name', 'code', 'start_date', 'end_date'):
            out[name]['required'] = True
    return out


# المخطط: نموذج -> حقوله (مطابق لـ OpenEduCat 17 Community)
SCHEMAS = {
    'op.academic.year': fields(name='char', start_date='date', end_date='date',
                               term_structure='selection', company_id='many2one'),
    'op.academic.term': fields(name='char', term_start_date='date',
                               term_end_date='date', academic_year_id='many2one',
                               parent_term='many2one'),
    'op.department': fields(name='char', code='char', parent_id='many2one'),
    'op.course': fields(name='char', code='char', parent_id='many2one',
                        evaluation_type='selection', subject_ids='many2many',
                        max_unit_load='float', min_unit_load='float',
                        department_id='many2one'),
    'op.subject': fields(name='char', code='char', grade_weightage='float',
                         type='selection', subject_type='selection',
                         department_id='many2one'),
    'op.batch': fields(code='char', name='char', start_date='date',
                       end_date='date', course_id='many2one'),
    'op.faculty': fields(partner_id='many2one', first_name='char',
                         middle_name='char', last_name='char',
                         birth_date='date', blood_group='selection',
                         gender='selection', nationality='many2one',
                         main_department_id='many2one',
                         faculty_subject_ids='many2many',
                         name='char', mobile='char', email='char',
                         street='char', city='char', zip='char',
                         country_id='many2one'),
    'op.student': fields(partner_id='many2one', first_name='char',
                         middle_name='char', last_name='char',
                         birth_date='date', blood_group='selection',
                         gender='selection', nationality='many2one',
                         gr_no='char', id_number='char',
                         name='char', mobile='char', email='char',
                         street='char', city='char', zip='char',
                         country_id='many2one'),
    'op.student.course': fields(student_id='many2one', course_id='many2one',
                                batch_id='many2one', roll_number='char',
                                subject_ids='many2many',
                                academic_years_id='many2one',
                                academic_term_id='many2one',
                                state='selection'),
    'op.admission.register': fields(name='char', start_date='date',
                                    end_date='date', course_id='many2one',
                                    min_count='integer', max_count='integer',
                                    product_id='many2one', state='selection',
                                    academic_years_id='many2one',
                                    minimum_age_criteria='integer'),
    'op.admission': fields(name='char', first_name='char', middle_name='char',
                           last_name='char', application_number='char',
                           application_date='datetime', birth_date='date',
                           course_id='many2one', batch_id='many2one',
                           street='char', phone='char', mobile='char',
                           email='char', city='char', fees='float',
                           state='selection', gender='selection',
                           student_id='many2one', register_id='many2one'),
    'op.exam.type': fields(name='char', code='char'),
    'op.exam.session': fields(name='char', course_id='many2one',
                              batch_id='many2one', exam_code='char',
                              start_date='date', end_date='date',
                              exam_type='many2one',
                              evaluation_type='selection', state='selection'),
    'op.exam': fields(session_id='many2one', subject_id='many2one',
                      exam_code='char', start_time='datetime',
                      end_time='datetime', state='selection',
                      responsible_id='many2many', name='char',
                      total_marks='integer', min_marks='integer'),
    'op.exam.attendees': fields(student_id='many2one', status='selection',
                                marks='integer', exam_id='many2one',
                                room_id='many2one'),
    'op.grade.configuration': fields(min_per='integer', max_per='integer',
                                     result='char'),
    'op.result.template': fields(exam_session_id='many2one', name='char',
                                 result_date='date',
                                 grade_ids='many2many', state='selection'),
    'op.marksheet.register': fields(exam_session_id='many2one', name='char',
                                    generated_date='date',
                                    result_template_id='many2one',
                                    state='selection'),
    'op.marksheet.line': fields(marksheet_reg_id='many2one',
                                student_id='many2one',
                                result_line='one2many',
                                generated_date='date', status='selection'),
    'op.result.line': fields(marksheet_line_id='many2one',
                             exam_id='many2one', marks='integer'),
    'op.fees.terms': fields(name='char', fees_terms='selection',
                            note='text', no_days='integer',
                            line_ids='one2many', company_id='many2one'),
    'op.fees.terms.line': fields(due_days='integer', due_date='date',
                                 value='float', fees_id='many2one'),
    'op.student.fees.details': fields(fees_line_id='many2one',
                                      invoice_id='many2one', amount='float',
                                      date='date', product_id='many2one',
                                      student_id='many2one', state='selection',
                                      course_id='many2one',
                                      batch_id='many2one'),
    'product.product': fields(name='char', type='selection',
                              list_price='float'),
    'res.country': fields(name='char', code='char'),
}
# خرائط one2many: (نموذج الأب، الحقل) -> (نموذج الابن، حقل الأب)
O2M = {
    ('op.marksheet.line', 'result_line'): ('op.result.line',
                                           'marksheet_line_id'),
    ('op.fees.terms', 'line_ids'): ('op.fees.terms.line', 'fees_id'),
}


class MockDB:
    def __init__(self):
        self.lock = threading.RLock()
        self.data = {m: {} for m in SCHEMAS}
        self.next = {m: 1 for m in SCHEMAS}
        # بيانات أساسية
        self.data['res.country'][1] = {'id': 1, 'name': 'Yemen', 'code': 'YE'}
        self.next['res.country'] = 2

    # ---- تقييم المجالات ----
    def _value_of(self, model, rec, field):
        val = rec.get(field, False)
        if isinstance(val, list) and len(val) == 2 and \
                SCHEMAS[model].get(field, {}).get('type') == 'many2one':
            return val[0]
        return val

    def _match(self, model, rec, domain):
        for term in domain:
            if isinstance(term, (list, tuple)):
                field, op, expected = term[0], term[1], term[2]
                if field == 'id':
                    val = rec['id']
                else:
                    val = self._value_of(model, rec, field)
                if op in ('=', '=='):
                    if not self._eq(val, expected):
                        return False
                elif op == '!=':
                    if self._eq(val, expected):
                        return False
                elif op == 'in':
                    if val not in expected and val not in [v for v in expected]:
                        return False
                elif op == 'ilike':
                    if str(expected).strip('%').lower() \
                            not in str(val or '').lower():
                        return False
                elif op == '=like':
                    pat = '^' + re.escape(str(expected)).replace('%', '.*') + '$'
                    if not re.match(pat, str(val or ''), re.IGNORECASE):
                        return False
                elif op == '>=':
                    if not (val is not False and val >= expected):
                        return False
                elif op == '<=':
                    if not (val is not False and val <= expected):
                        return False
                elif op == '>':
                    if not (val is not False and val > expected):
                        return False
                elif op == '<':
                    if not (val is not False and val < expected):
                        return False
        return True

    @staticmethod
    def _eq(a, b):
        if a is False and (b is None or b is False):
            return True
        return a == b

    def search(self, model, domain):
        with self.lock:
            return [rid for rid, rec in sorted(self.data[model].items())
                    if self._match(model, rec, domain or [])]

    def read(self, model, ids, flds=None):
        with self.lock:
            out = []
            for rid in ids:
                rec = self.data[model].get(rid)
                if not rec:
                    continue
                row = {'id': rid}
                for f in (flds or list(SCHEMAS[model].keys())):
                    if f == 'id':
                        continue
                    val = rec.get(f, False)
                    ftype = SCHEMAS[model].get(f, {}).get('type', 'char')
                    if ftype == 'many2one' and isinstance(val, int):
                        nm = self.data['res.country'].get(val, {}) \
                            if model.startswith('res.') else None
                        row[f] = [val, (nm or {}).get('name', 'Record %d' % val)]
                    else:
                        row[f] = val
                out.append(row)
            return out

    def create(self, model, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        with self.lock:
            ids = []
            for vals in vals_list:
                vals = dict(vals)
                rid = self.next[model]
                self.next[model] += 1
                rec = {'id': rid}
                for k, v in vals.items():
                    if k not in SCHEMAS[model]:
                        continue  # تجاهل حقول غير معروفة (تسامح الاختبار)
                    ftype = SCHEMAS[model][k]['type']
                    if ftype == 'many2many' and isinstance(v, list) and v \
                            and isinstance(v[0], (list, tuple)) and v[0][0] == 6:
                        rec[k] = list(v[0][2])
                    elif (model, k) in O2M and isinstance(v, list):
                        child_model, parent_field = O2M[(model, k)]
                        child_ids = []
                        for cmd in v:
                            if isinstance(cmd, (list, tuple)) and cmd[0] == 0:
                                cvals = dict(cmd[2])
                                cvals[parent_field] = rid
                                cid = self.next[child_model]
                                self.next[child_model] += 1
                                self.data[child_model][cid] = dict(
                                    cvals, id=cid)
                                child_ids.append(cid)
                        rec[k] = child_ids
                    else:
                        rec[k] = v
                # توليد رقم الطلب تلقائياً كما يفعل القيد في admission
                if model == 'op.admission' and not rec.get('application_number'):
                    rec['application_number'] = 'AD%05d' % rid
                self.data[model][rid] = rec
                ids.append(rid)
            return ids

    def write(self, model, ids, vals):
        with self.lock:
            for rid in ids:
                rec = self.data[model].get(rid)
                if not rec:
                    continue
                for k, v in vals.items():
                    if k not in SCHEMAS[model]:
                        continue
                    if SCHEMAS[model][k]['type'] == 'many2many' and \
                            isinstance(v, list) and v and v[0][0] == 6:
                        rec[k] = list(v[0][2])
                    else:
                        rec[k] = v
            return True

    def unlink(self, model, ids):
        with self.lock:
            for rid in ids:
                self.data[model].pop(rid, None)
            return True

    def fields_get(self, model):
        return SCHEMAS[model]

    def stats(self):
        with self.lock:
            return {m: len(self.data[m]) for m in sorted(self.data)
                    if self.data[m]}


DB = MockDB()


class Handler(SimpleXMLRPCRequestHandler):
    rpc_paths = None  # قبول أي مسار (/xmlrpc/2/common و /xmlrpc/2/object)

    def _dispatch(self, method, params):
        if method == 'authenticate':
            return 2
        if method == 'execute':
            args = list(params)
            return self._execute(args[0], args[1], args[2], args[3],
                                 args[4], args[5], {})
        if method == 'execute_kw':
            args = list(params)
            kwargs = args[-1] if isinstance(args[-1], dict) else {}
            if isinstance(args[-1], dict):
                args = args[:-1]
            return self._execute(args[0], args[1], args[2], args[3],
                                 args[4], args[5], kwargs)
        raise Exception('method %s not found' % method)

    def _execute(self, db, uid, pwd, model, method, args, kwargs):
        if model == 'ir.model' and method == 'search_read':
            dom = args[0] if args else kwargs.get('args', [])
            models = [m for m in SCHEMAS if m.startswith('op.')]
            return [{'model': m, 'name': m, 'id': i}
                    for i, m in enumerate(models)
                    if self._model_match(m, dom)]
        if model == 'ir.model' and method == 'search':
            dom = args[0] if args else kwargs.get('args', [])
            return [i for i, m in enumerate(
                [m2 for m2 in SCHEMAS if m2.startswith('op.')])
                if self._model_match(m, dom)]
        if model not in SCHEMAS and model != 'ir.model':
            raise Exception('النموذج غير موجود: %s' % model)
        if method == 'search':
            return DB.search(model, args[0] if args else [])
        if method == 'search_count':
            return len(DB.search(model, args[0] if args else []))
        if method == 'search_read':
            dom = args[0] if args else []
            flds = kwargs.get('fields') or (args[1] if len(args) > 1 else None)
            ids = DB.search(model, dom)
            limit = kwargs.get('limit')
            offset = kwargs.get('offset', 0)
            if offset:
                ids = ids[offset:]
            if limit:
                ids = ids[:limit]
            return DB.read(model, ids, flds)
        if method == 'read':
            return DB.read(model, args[0], args[1] if len(args) > 1 else None)
        if method == 'create':
            return DB.create(model, args[0])
        if method == 'write':
            return DB.write(model, args[0], args[1])
        if method == 'unlink':
            return DB.unlink(model, args[0])
        if method == 'fields_get':
            return DB.fields_get(model)
        raise Exception('method %s not supported on %s' % (method, model))

    @staticmethod
    def _model_match(m, dom):
        for term in dom or []:
            if term[1] in ('=like', 'ilike', 'like'):
                pat = str(term[2])
                if pat.startswith('%') and pat.endswith('%'):
                    return pat.strip('%') in m
                if pat.endswith('%'):
                    return m.startswith(pat[:-1])
                if pat.startswith('%'):
                    return m.endswith(pat[1:])
                return m == pat
            if term[1] == '=' and term[0] == 'model':
                return m == term[2]
        return True


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8169
    server = SimpleXMLRPCServer(('127.0.0.1', port), requestHandler=Handler,
                                 allow_none=True, logRequests=False)
    print('Mock Odoo XML-RPC على المنفذ %d (Ctrl+C للإيقاف)' % port)
    print('إحصاءات النماذج تُطبع كل 30 ثانية')
    server.serve_forever()


if __name__ == '__main__':
    main()
