#!/bin/bash
# =============================================================================
# غلاف نقطة دخول حاوية أودو:
#   1) ينتظر جاهزية PostgreSQL.
#   2) عند أول تشغيل فقط (أو عندما تكون قاعدة البيانات فارغة/بدون وحدات):
#      يثبّت وحدات OpenEduCat الأربع + اللغة العربية ثم يخرج.
#   3) يسلّم التنفيذ لنقطة الدخول الرسمية للصورة (تشغيل الخادم).
# =============================================================================
set -e

DB_NAME="${DB_NAME:-university}"
MODULES="${MODULES:-openeducat_core,openeducat_admission,openeducat_exam,openeducat_fees}"
LOAD_LANG="${LOAD_LANG:-ar_001}"

wait_for_db() {
    echo ">>> Waiting for PostgreSQL at ${HOST:-db}:${PORT:-5432} ..."
    python3 - <<'PY'
import os, sys, time
import psycopg2
host = os.environ.get('HOST', 'db')
port = int(os.environ.get('PORT', '5432'))
user = os.environ.get('USER', 'odoo')
password = os.environ.get('PASSWORD', 'odoo')
for i in range(120):
    try:
        psycopg2.connect(host=host, port=port, user=user, password=password,
                          dbname='postgres', connect_timeout=5)
        sys.exit(0)
    except Exception:
        time.sleep(2)
sys.exit(1)
PY
}

need_init() {
    python3 - <<'PY'
import os, sys
import psycopg2
host = os.environ.get('HOST', 'db')
port = int(os.environ.get('PORT', '5432'))
user = os.environ.get('USER', 'odoo')
password = os.environ.get('PASSWORD', 'odoo')
db = os.environ.get('DB_NAME', 'university')
try:
    conn = psycopg2.connect(host=host, port=port, user=user, password=password,
                             dbname=db, connect_timeout=5)
except psycopg2.OperationalError:
    sys.exit(0)          # القاعدة غير موجودة أصلاً → يحتاج تهيئة
try:
    cur = conn.cursor()
    cur.execute("SELECT state FROM ir_module_module WHERE name='openeducat_core'")
    row = cur.fetchone()
except psycopg2.Error:
    sys.exit(0)          # القاعدة موجودة لكنها فارغة → يحتاج تهيئة
sys.exit(0 if (row and row[0] == 'installed') else 1)
PY
}

wait_for_db

if need_init; then
    echo ">>> First-time setup: installing OpenEduCat modules + Arabic language ..."
    echo ">>> (this runs once; it takes 3-10 minutes depending on your machine)"
    /entrypoint.sh odoo -d "$DB_NAME" -i "$MODULES" \
        --load-language="$LOAD_LANG" --without-demo=all --stop-after-init
    echo ">>> Module installation finished."
else
    echo ">>> Database '$DB_NAME' already initialized — starting Odoo."
fi

exec /entrypoint.sh "$@"
