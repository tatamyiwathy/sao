import logging

class TestPrefixFormatter(logging.Formatter):
    def format(self, record):
        # 例えば環境変数や settings などで判定
        import os
        if os.environ.get("IS_TEST"):
            record.msg = "" + str(record.msg)
        return super().format(record)