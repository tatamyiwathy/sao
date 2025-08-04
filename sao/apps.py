from __future__ import unicode_literals

from django.apps import AppConfig
import logging


class SaoConfig(AppConfig):
    name = 'sao'
    def ready(self):
        # このタイミングならログ設定が完了している
        logger = logging.getLogger("sao")
        logger.info("SAO application ready")