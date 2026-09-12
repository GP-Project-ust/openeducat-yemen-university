#!/bin/bash
# =============================================================================
# يُنفَّذ تلقائياً داخل حاوية PostgreSQL عند أول إنشاء للبيانات فقط
# (مجلد docker-entrypoint-initdb.d في الصورة الرسمية).
# يستعيد نسخة قاعدة البيانات الجاهزة المولّدة مسبقاً (جامعة يمنية كاملة)
# إن وُجدت — وإلا يترك القاعدة فارغة ليقوم غلاف أودو بالتثبيت من الصفر.
# =============================================================================
set -e

DUMP=/dumps/university.dump

if [ -f "$DUMP" ]; then
    echo ">>> Restoring pre-seeded Yemen university database ..."
    pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
        --no-owner --no-privileges "$DUMP"
    echo ">>> Restore complete: $(pg_restore -U "$POSTGRES_USER" -l "$DUMP" | grep -c 'TABLE DATA' ) data tables loaded."
else
    echo ">>> No seed dump found at db_dumps/university.dump"
    echo ">>> The Odoo container will install modules and you can seed data via:"
    echo ">>>   docker compose --profile seed run --rm seeder"
fi
