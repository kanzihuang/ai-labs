ENCRYPT_KEY ?= mysecretkey
CONF_DIR = conf
ENCRYPTED_DIR = conf_encrypted
TAG ?= curl-batch

CURL_FILES = $(wildcard $(CONF_DIR)/*.curl)
ENCRYPTED_FILES = $(patsubst $(CONF_DIR)/%.curl,$(ENCRYPTED_DIR)/%.curl.enc,$(CURL_FILES))

.PHONY: all encrypt clean build

all: build

encrypt: $(ENCRYPTED_FILES)

$(ENCRYPTED_DIR)/%.curl.enc: $(CONF_DIR)/%.curl
	@mkdir -p $(ENCRYPTED_DIR)
	openssl enc -aes-256-cbc -salt -pbkdf2 -in $< -out $@ -k $(ENCRYPT_KEY)

# 用法：make build [TAG=your-tag]
build: encrypt
	docker build -t $(TAG) .

clean:
	rm -rf $(ENCRYPTED_DIR)
