#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
 bootstrap.py — تهيئة النظام بعد التثبيت الأول (Odoo 17 + OpenEduCat)
==============================================================================
 خطواته (كلها آمنة قابلة لإعادة التشغيل Idempotent):
   1) تفعيل اللغة العربية (ar_001) وتحميل ترجمات الوحدات المثبتة.
   2) ضبط مستخدم admin: اللغة عربية + المنطقة الزمنية Asia/Aden.
   3) هوية الجامعة: الاسم العربي + العلم اليمني + عملة الريال اليمني YER.
   4) خيار --generate لتشغيل مولّد البيانات مباشرة بعد التهيئة.

 مثال:
   python3 bootstrap.py --url http://localhost:8069 --db university \
        --user admin --password admin

   python3 bootstrap.py --url http://localhost:8069 --db university \
        --user admin --password admin --generate -- --preset full --yes

 يعمل عبر XML-RPC فقط (نفس مسار ORM الرسمي) — لا SQL مباشر إطلاقاً.
 المتطلبات: Python 3.8+ فقط (مكتبة xmlrpc.client المدمجة).
==============================================================================
"""

import argparse
import os
import subprocess
import sys
import time
import xmlrpc.client

UNIVERSITY_NAME_DEFAULT = 'جامعة اليمن الأهلية'
LANG_CODE = 'ar_001'
ADMIN_TZ = 'Asia/Aden'

ENV = {k: os.environ.get(v) for k, v in [
    ('url', 'ODOO_URL'), ('db', 'ODOO_DB'),
    ('user', 'ODOO_USER'), ('password', 'ODOO_PASSWORD')]}


def build_parser():
    p = argparse.ArgumentParser(
        prog='bootstrap.py',
        description='تهيئة اللغة العربية وهوية الجامعة بعد تثبيت OpenEduCat')
    p.add_argument('--url', default=ENV['url'] or 'http://localhost:8069',
                   help='رابط خادم أودو')
    p.add_argument('--db', default=ENV['db'] or 'university',
                   help='اسم قاعدة البيانات')
    p.add_argument('--user', default=ENV['user'] or 'admin',
                   help='المستخدم المدير')
    p.add_argument('--password', default=ENV['password'] or 'admin',
                   help='كلمة المرور')
    p.add_argument('--university-name', default=UNIVERSITY_NAME_DEFAULT,
                   help='اسم الجامعة الظاهر في النظام')
    p.add_argument('--generate', action='store_true',
                   help='تشغيل مولّد البيانات بعد التهيئة')
    p.add_argument('gen_args', nargs=argparse.REMAINDER, default=[],
                   help="وسائط إضافية تُمرر للمولّد بعد '--' "
                        "(مثال: -- --preset full --yes)")
    return p


class Odoo:
    def __init__(self, url, db, user, password, retries=1, wait=3):
        self.db, self.password = db, password
        self.url = url.rstrip('/')
        self.common = xmlrpc.client.ServerProxy(
            self.url + '/xmlrpc/2/common', allow_none=True)
        self.models = xmlrpc.client.ServerProxy(
            self.url + '/xmlrpc/2/object', allow_none=True)
        self.uid = None
        for attempt in range(max(1, retries)):
            try:
                self.uid = self.common.authenticate(db, user, password, {})
                if self.uid:
                    break
            except OSError:
                pass
            if attempt < retries - 1:
                print('[bootstrap] في انتظار جاهزية الخادم... (%d/%d)'
                      % (attempt + 1, retries))
                time.sleep(wait)
        if not self.uid:
            raise SystemExit(
                'فشل تسجيل الدخول — تحقق من الرابط/القاعدة/المستخدم/كلمة المرور '
                '(انتظر جاهزية خادم أودو ثم أعد المحاولة)')

    def ex(self, model, method, *args, **kw):
        return self.models.execute_kw(
            self.db, self.uid, self.password, model, method, list(args), kw)

    def search(self, model, domain, fields=None, limit=None):
        kw = {}
        if fields:
            kw['fields'] = fields
        if limit:
            kw['limit'] = limit
        return self.ex(model, 'search_read', domain, **kw)


def step_ensure_arabic(odoo, log):
    """1) تفعيل العربية إن لم تكن مفعلة + تحميل الترجمات."""
    langs = odoo.search('res.lang', [('code', '=', LANG_CODE)], ['code', 'active'])
    if langs and langs[0]['active']:
        log('اللغة العربية (ar_001) مفعلة مسبقاً — تخطي التحميل.')
        return
    log('تفعيل اللغة العربية وتحميل ترجمات الوحدات... (قد يستغرق دقيقة)')
    wiz_id = odoo.ex('base.language.install', 'create', [{'lang_code': LANG_CODE}])
    odoo.ex('base.language.install', 'lang_install', [wiz_id])
    log('تم تفعيل اللغة العربية.')


def step_configure_admin(odoo, log):
    """2) لغة المستخدم المدير + المنطقة الزمنية."""
    vals = {}
    me = odoo.ex('res.users', 'read', odoo.uid, ['lang', 'tz', 'name'])
    if me[0]['lang'] != LANG_CODE:
        vals['lang'] = LANG_CODE
    if me[0]['tz'] != ADMIN_TZ:
        vals['tz'] = ADMIN_TZ
    if vals:
        odoo.ex('res.users', 'write', [odoo.uid], vals)
        log('ضبط مستخدم المدير: اللغة عربية + المنطقة الزمنية %s.' % ADMIN_TZ)
    else:
        log('مستخدم المدير مضبوط مسبقاً.')
    # اسم عربي للمدير (إن كان الاسم الافتراضي الإنجليزي)
    if me[0].get('name', '') in ('Administrator', 'My User'):
        try:
            odoo.ex('res.users', 'write', [odoo.uid], {'name': 'مدير النظام'})
            log('اسم مستخدم المدير: مدير النظام.')
        except Exception:
            pass  # غير حرج


def step_university_identity(odoo, log, name):
    """3) هوية الجامعة: الاسم + البلد + العملة."""
    comp = odoo.ex('res.company', 'read', [1], ['name', 'partner_id', 'currency_id'])[0]
    partner_id = comp['partner_id'][0]
    partner = odoo.ex('res.partner', 'read', [partner_id], ['name', 'country_id'])[0]

    if partner['name'] != name:
        odoo.ex('res.partner', 'write', [partner_id], {'name': name})
        log('اسم الجامعة: %s' % name)

    if not partner['country_id'] or partner['country_id'][1] != 'Yemen':
        ctry = odoo.search('res.country', [('code', '=', 'YE')], ['id'], limit=1)
        if ctry:
            odoo.ex('res.partner', 'write', [partner_id], {'country_id': ctry[0]['id']})
            log('بلد الجامعة: اليمن.')

    cur_name = comp['currency_id'][1] if comp['currency_id'] else None
    if cur_name != 'YER':
        # العملة موجودة في بيانات أودو لكنها غير مفعلة — ابحث مع تجاهل active
        yer = odoo.ex('res.currency', 'search_read',
                       [('name', '=', 'YER')], ['id', 'active'],
                       context={'active_test': False})
        if yer:
            yer_id = yer[0]['id']
            try:
                if not yer[0]['active']:
                    odoo.ex('res.currency', 'write', [yer_id], {'active': True})
                    log('تفعيل عملة الريال اليمني (YER).')
                # تأمين سجل سعر صرف ابتدائي = 1.0 (عملة الشركة نفسها)
                rates = odoo.ex('res.currency.rate', 'search_read',
                                [('currency_id', '=', yer_id)], ['id'], limit=1)
                if not rates:
                    import datetime
                    odoo.ex('res.currency.rate', 'create', [{
                        'currency_id': yer_id, 'rate': 1.0,
                        'name': datetime.date.today().isoformat()}])
                    log('سجل سعر صرف ابتدائي 1.0 للعملة.')
                odoo.ex('res.company', 'write', [1], {'currency_id': yer_id})
                log('عملة النظام: الريال اليمني (YER).')
            except Exception as e:
                log('تنبيه: تعذر تغيير عملة الشركة (%s) — استمرار بالعملة الحالية.' % e)
        else:
            log('تنبيه: عملة YER غير موجودة في القاعدة — تخطي الخطوة.')


def step_openeducat_admin_fixes(odoo, log):
    """4) ترقيع صلاحية ناقصة في OpenEduCat Community 17:
    لا يملك أي دور حق حذف سجلات حضور الامتحانات (op.exam.attendees)،
    وهو ما يحتاجه أمر --purge في مولّد البيانات. نضيف سطر صلاحية
    واحد لدور «مدير الامتحانات» (مثل أي تخصيص يُعمل من شاشة الصلاحيات).
    """
    model = odoo.search('ir.model', [('model', '=', 'op.exam.attendees')],
                        ['id'], limit=1)
    if not model:
        log('تنبيه: نموذج op.exam.attendees غير موجود — تخطي ترقيع الصلاحية.')
        return
    model_id = model[0]['id']
    existing = odoo.ex(
        'ir.model.access', 'search_read',
        [('model_id', '=', model_id), ('perm_unlink', '=', True)],
        ['id', 'name'], limit=1)
    if existing:
        log('صلاحية حذف سجلات الحضور موجودة — تخطي.')
        return
    # دور مدير الامتحانات: openeducat_exam.group_op_exam_admin
    ref = odoo.search('ir.model.data',
                      [('module', '=', 'openeducat_exam'),
                       ('name', '=', 'group_op_exam_admin')],
                      ['res_id'], limit=1)
    if not ref:
        log('تنبيه: لم يُعثر على دور مدير الامتحانات — تخطي ترقيع الصلاحية.')
        return
    odoo.ex('ir.model.access', 'create', [{
        'name': 'access_op_exam_attendees_exam_admin_delete',
        'model_id': model_id,
        'group_id': ref[0]['res_id'],
        'perm_read': True, 'perm_write': True,
        'perm_create': True, 'perm_unlink': True,
    }])
    log('أضيف سطر صلاحية: حذف سجلات حضور الامتحانات لدور مدير الامتحانات '
        '(ناقص في Community 17 — يلزم لأمر --purge).')


def main():
    args = build_parser().parse_args()

    def log(msg):
        print('[bootstrap] %s' % msg)

    log('الاتصال بـ %s (قاعدة: %s) ...' % (args.url, args.db))
    # حتى 60 محاولة × 5 ثوانٍ: ينتظر جاهزية خادم أودو (مفيد لحاوية seeder)
    odoo = Odoo(args.url, args.db, args.user, args.password,
                retries=60, wait=5)
    log('تم الدخول بنجاح (uid=%s).' % odoo.uid)

    step_ensure_arabic(odoo, log)
    step_configure_admin(odoo, log)
    step_university_identity(odoo, log, args.university_name)
    step_openeducat_admin_fixes(odoo, log)
    log('اكتملت التهيئة — النظام عربي بالكامل وجاهز.')

    if args.generate:
        gen_args = [a for a in args.gen_args if a != '--']
        gen_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'openeducat_yemen_generator.py')
        if not os.path.exists(gen_path):
            raise SystemExit('لم يتم العثور على المولّد بجانب السكريبت: %s' % gen_path)
        cmd = [sys.executable, gen_path,
               '--url', args.url, '--db', args.db,
               '--user', args.user, '--password', args.password] + gen_args
        log('تشغيل مولّد البيانات: %s' % ' '.join(cmd))
        rc = subprocess.call(cmd)
        raise SystemExit(rc)


if __name__ == '__main__':
    main()
