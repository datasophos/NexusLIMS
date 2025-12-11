#!/bin/bash
# MongoDB initialization script for NexusLIMS CDCS test environment
# Creates the CDCS database user with read/write permissions

set -e

echo "Creating CDCS user in MongoDB..."

mongosh <<EOF
use admin
db.auth('${MONGO_INITDB_ROOT_USERNAME}', '${MONGO_INITDB_ROOT_PASSWORD}')

use ${MONGO_INITDB_DATABASE}
db.createUser({
    user: '${MONGO_USER}',
    pwd: '${MONGO_PASS}',
    roles: [
        {
            role: 'readWrite',
            db: '${MONGO_INITDB_DATABASE}'
        }
    ]
})

print('CDCS user created successfully')
EOF

echo "MongoDB initialization complete"
