# colorscheme janah darkVG

# makes CA certificates, server certificates, and client certificates
# based on https://chatgpt.com/share/e/b30d1f31-1c70-48c7-a59f-8c7fdf859d61


from cryptography.hazmat.primitives.asymmetric import rsa
from ipaddress import ip_address
from cryptography.hazmat.primitives import serialization, hashes
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.x509 import load_pem_x509_certificate
import datetime
from pathlib import Path

import logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def make_ca_authority_and_server(hostname, 
                                 outdir, 
                                 country_name = "ZA", 
                                 state_or_province_name = "Gauteng", 
                                 locality_name = "Johannesburg", 
                                 organization_name = "Zombie CA Organization", 
                                 common_name = "ZombieCA"):

    # Generate the CA private key
    ca_private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    # Save the private key to a file
    with open(outdir / "ca_private_key.pem", "wb") as key_file:
        key_file.write(
            ca_private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()  # You can use a password if needed
            )
        )

    logger.info("CA private key generated and saved.")

    # Create a builder for the CA certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, country_name),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state_or_province_name),
        x509.NameAttribute(NameOID.LOCALITY_NAME, locality_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization_name),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    ca_certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(ca_private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))  # 10 years validity
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True,
        )
        .sign(ca_private_key, hashes.SHA256())  # Use correct 'hashes' here
    )

    # Save the self-signed CA certificate
    with open(outdir / "ca_certificate.pem", "wb") as cert_file:
        cert_file.write(ca_certificate.public_bytes(serialization.Encoding.PEM))

    logger.info(f"Self-signed CA certificate generated and saved to {outdir}.")

    # Generate the server private key
    server_private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    # Define the server subject with the domain name in the CN field
    server_subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, country_name), 
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state_or_province_name),
        x509.NameAttribute(NameOID.LOCALITY_NAME, locality_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization_name),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),  # Server's domain name
    ])

    # Create the server CSR
    csr = x509.CertificateSigningRequestBuilder().subject_name(server_subject)

    # Add Subject Alternative Name (SAN) extension to support the domain name
    csr = csr.add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName("signaliser.com")
        ]), critical=False
    )

    # Sign the CSR with the server's private key
    csr = csr.sign(server_private_key, hashes.SHA256())

    # Issue the server certificate using the CA
    server_certificate = (
        x509.CertificateBuilder()
        .subject_name(csr.subject)
        .issuer_name(ca_certificate.subject)  # CA is the issuer
        .public_key(server_private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))  # 1 year validity
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True,
        )
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName(hostname)
            ]), critical=False
        )
        .sign(ca_private_key, hashes.SHA256())
    )

    # Save server private key and certificate
    with open(outdir / "server_private_key.pem", "wb") as key_file:
        key_file.write(
            server_private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    with open(outdir / "server_certificate.pem", "wb") as cert_file:
        cert_file.write(server_certificate.public_bytes(serialization.Encoding.PEM))

    logger.info(f"Server certificate for {hostname} and private key saved to {outdir}.")


def read_ca_authority_and_server(outdir, password=None):
    # Load the CA private key from the file
    with open(outdir / "ca_private_key.pem", "rb") as key_file:
        ca_private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=password  # None if no password, or provide one if needed
        )
    # Load the CA certificate from the file
    with open(outdir / "ca_certificate.pem", "rb") as cert_file:
        ca_certificate = load_pem_x509_certificate(cert_file.read())
    return ca_private_key, ca_certificate
#------------------------------------------- client grpc

def make_client_certs(hostname,
                      confdir,
                      country_name = "ZA", 
                      state_or_province_name = "Gauteng", 
                      locality_name = "Johannesburg", 
                      organization_name = "Zombie CA Organization", 
                      common_name = "ZombieCA"):
    # Generate client private key
    client_private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    ca_private_key, ca_certificate = read_ca_authority_and_server(confdir)

    # Create client certificate request
    client_subject = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, country_name), 
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state_or_province_name),
        x509.NameAttribute(NameOID.LOCALITY_NAME, locality_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization_name),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),  # Server's domain name
    ])

    csr = x509.CertificateSigningRequestBuilder().subject_name(client_subject).sign(
        client_private_key, hashes.SHA256()
    )

    # Issue the client certificate using the CA
    client_certificate = (
        x509.CertificateBuilder()
        .subject_name(csr.subject)
        .issuer_name(ca_certificate.subject)
        .public_key(client_private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))  # 1 year validity
        .sign(ca_private_key, hashes.SHA256())
    )

    # Save client private key and certificate
    key = client_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )

    cert = client_certificate.public_bytes(serialization.Encoding.PEM)

    return key, cert, ca_certificate



def get_conf_dir():
    return Path.home() / ".config/gBLP"


def make_all_certs(hostname, outdir = get_conf_dir()):
    # make CA authority, make cerver certs, make client certs, 
    # save to outdir
    outdir = get_conf_dir()
    outdir.mkdir(parents=True, exist_ok=True)

    make_ca_authority_and_server(hostname, outdir)

    clkey, clcert, cacert = make_client_certs(hostname, outdir)
    with open(outdir / "client_private_key.pem", "wb") as key_file:
        key_file.write(clkey)
    with open(outdir / "client_certificate.pem", "wb") as cert_file:
        cert_file.write(clcert)
    logger.info(f"Client certificate and private key saved to {outdir}.")


if __name__ == "__main__":
    # pathlib make from home directory ~/.config/gblp/ if it does not exist
    outdir = get_conf_dir() 
    outdir.mkdir(parents=True, exist_ok=True)

    make_all_certs("signaliser.com", outdir)

