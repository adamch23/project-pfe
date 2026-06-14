
import os
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

def generate_self_signed_cert(cert_dir):
    if not os.path.exists(cert_dir):
        os.makedirs(cert_dir)
        print(f"Directory {cert_dir} created.")

    key_path = os.path.join(cert_dir, "server.key")
    cert_path = os.path.join(cert_dir, "server.crt")

    # Generate key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
    )

    # Write key
    with open(key_path, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))

    # Generate CSR/Cert
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "TN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Tunis"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Tunis"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Attijari Bank"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        # Our certificate will be valid for 1 year
        datetime.utcnow() + timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([x509.DNSName("localhost")]),
        critical=False,
    ).sign(key, hashes.SHA256())

    # Write cert
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    print(f"Certificates generated in {cert_dir}")

if __name__ == "__main__":
    # Generate for the default certs dir used in docker-compose.yml
    generate_self_signed_cert("e:/certs")
    # Also generate for the prod dir mentioned in docker-compose.prod.yml if needed
    generate_self_signed_cert("e:/certs/prod")
