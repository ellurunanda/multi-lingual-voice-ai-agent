ALTER USER postgres WITH PASSWORD 'postgres';
CREATE USER voiceai WITH PASSWORD 'voiceai_password';
CREATE DATABASE voiceai_db OWNER voiceai;
GRANT ALL PRIVILEGES ON DATABASE voiceai_db TO voiceai;