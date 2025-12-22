check: check-license check-banwords

check-license:
	scripts/licensing/licensing.py

check-banwords:
	scripts/banwords/banwords.py

.PHONY: check check-license check-banwords
