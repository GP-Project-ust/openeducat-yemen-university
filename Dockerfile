# =============================================================================
# صورة Odoo 17 + OpenEduCat Community 17 — جامعة يمنية عربية جاهزة
# =============================================================================
FROM odoo:17.0

USER root

# git لاستنساخ OpenEduCat وقت البناء
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# استنساخ OpenEduCat Community (فرع 17.0) داخل مسار الإضافات
RUN git clone --depth 1 --branch 17.0 \
        https://github.com/openeducat/openeducat_erp.git \
        /mnt/extra-addons/openeducat_erp \
    && rm -rf /mnt/extra-addons/openeducat_erp/.git \
    && chown -R odoo:odoo /mnt/extra-addons

# سكربتات المشروع (المولّد + التهيئة العربية + السيرفر الوهمي)
COPY scripts/ /opt/scripts/
RUN chmod 755 /opt/scripts/*.py

# غلاف نقطة الدخول: انتظار قاعدة البيانات + تثبيت تلقائي أول مرة
COPY entrypoint-wrapper.sh /
RUN chmod 755 /entrypoint-wrapper.sh

USER odoo

ENTRYPOINT ["/entrypoint-wrapper.sh"]
CMD ["odoo"]
