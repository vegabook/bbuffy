# colorscheme janah dark

# makes CA certificates, server certificates, and client certificates
# based on https://chatgpt.com/share/e/b30d1f31-1c70-48c7-a59f-8c7fdf859d61

OUTDIR = "../../certs/out/pycerts/"

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# Generate the CA private key
ca_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

# Save the private key to a file
with open(OUTDIR + "ca_private_key.pem", "wb") as key_file:
    key_file.write(
        ca_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()  # You can use a password if needed
        )
    )

print("CA private key generated and saved.")


# ----------------------------

from cryptography.x509.oid import NameOID
from cryptography import x509
from cryptography.hazmat.primitives import hashes  # Corrected import for hashes
import datetime

# Create a builder for the CA certificate
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"California"),
    x509.NameAttribute(NameOID.LOCALITY_NAME, u"San Francisco"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"My CA Organization"),
    x509.NameAttribute(NameOID.COMMON_NAME, u"My Root CA"),
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
    .sign(ca_private_key, hashes.SHA256(), default_backend())  # Use correct 'hashes' here
)

# Save the self-signed CA certificate
with open(OUTDIR + "ca_certificate.pem", "wb") as cert_file:
    cert_file.write(ca_certificate.public_bytes(serialization.Encoding.PEM))

print("Self-signed CA certificate generated and saved.")
# Generate a private key for the user

# --------------------------------------------

user_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

# Create a certificate signing request (CSR)
user_subject = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"California"),
    x509.NameAttribute(NameOID.LOCALITY_NAME, u"San Francisco"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"My User Organization"),
    x509.NameAttribute(NameOID.COMMON_NAME, u"User Certificate"),
])

csr = x509.CertificateSigningRequestBuilder().subject_name(user_subject).sign(
    user_private_key, hashes.SHA256(), default_backend()
)

# Issue the certificate using the CA
user_certificate = (
    x509.CertificateBuilder()
    .subject_name(csr.subject)
    .issuer_name(ca_certificate.subject)
    .public_key(user_private_key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.utcnow())
    .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))  # 1 year validity
    .sign(ca_private_key, hashes.SHA256(), default_backend())
)

# Save the user certificate
with open(OUTDIR + "user_certificate.pem", "wb") as cert_file:
    cert_file.write(user_certificate.public_bytes(serialization.Encoding.PEM))

print("User certificate generated and saved.")

# -------------------------------------------- server grpc
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization, hashes
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.backends import default_backend
import datetime

# Generate the server private key
server_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

# Define the server subject with the domain name in the CN field
server_subject = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"California"),
    x509.NameAttribute(NameOID.LOCALITY_NAME, u"San Francisco"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"My Server Organization"),
    x509.NameAttribute(NameOID.COMMON_NAME, u"signaliser.com"),  # Server's domain name
])

# Create the server CSR
csr = x509.CertificateSigningRequestBuilder().subject_name(server_subject)

# Add Subject Alternative Name (SAN) extension to support the domain name
csr = csr.add_extension(
    x509.SubjectAlternativeName([x509.DNSName(u"signaliser.com")]), critical=False
)

# Sign the CSR with the server's private key
csr = csr.sign(server_private_key, hashes.SHA256(), default_backend())

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
        x509.SubjectAlternativeName([x509.DNSName(u"signaliser.com")]), critical=False
    )
    .sign(ca_private_key, hashes.SHA256(), default_backend())
)

# Save server private key and certificate
with open(OUTDIR + "server_private_key.pem", "wb") as key_file:
    key_file.write(
        server_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

with open(OUTDIR + "server_certificate.pem", "wb") as cert_file:
    cert_file.write(server_certificate.public_bytes(serialization.Encoding.PEM))

print("Server certificate for 'signaliser.com' and private key saved.")




#------------------------------------------- client grpc


# Generate client private key
client_private_key = rsa.generate_private_key(
    public_exponent=65537,
    key_size=2048,
    backend=default_backend()
)

# Create client certificate request
client_subject = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, u"US"),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"California"),
    x509.NameAttribute(NameOID.LOCALITY_NAME, u"San Francisco"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"My Client Organization"),
    x509.NameAttribute(NameOID.COMMON_NAME, u"client"),
])

csr = x509.CertificateSigningRequestBuilder().subject_name(client_subject).sign(
    client_private_key, hashes.SHA256(), default_backend()
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
    .sign(ca_private_key, hashes.SHA256(), default_backend())
)

# Save client private key and certificate
with open(OUTDIR + "client_private_key.pem", "wb") as key_file:
    key_file.write(
        client_private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

with open(OUTDIR + "client_certificate.pem", "wb") as cert_file:
    cert_file.write(client_certificate.public_bytes(serialization.Encoding.PEM))

print("Client certificate and private key saved.")


# -------------------------------- server credentials

import grpc
from concurrent import futures

# Load server's certificate and private key
with open(OUTDIR+"server_certificate.pem", "rb") as f:
    server_cert = f.read()

with open(OUTDIR+"server_private_key.pem", "rb") as f:
    server_key = f.read()

# Load CA certificate to verify clients
with open(OUTDIR+"ca_certificate.pem", "rb") as f:
    ca_cert = f.read()

# Create SSL credentials for the server
server_credentials = grpc.ssl_server_credentials(
    [(server_key, server_cert)],
    root_certificates=ca_cert,
    require_client_auth=True,  # Require clients to provide valid certificates
)


# -------------------------------- client credentials
import grpc

# Load client's certificate and private key
with open(OUTDIR+"client_certificate.pem", "rb") as f:
    client_cert = f.read()

with open(OUTDIR+"client_private_key.pem", "rb") as f:
    client_key = f.read()

# Load CA certificate to verify the server
with open(OUTDIR+"ca_certificate.pem", "rb") as f:
    ca_cert = f.read()

# Create SSL credentials for the client
client_credentials = grpc.ssl_channel_credentials(
    root_certificates=ca_cert,
    private_key=client_key,
    certificate_chain=client_cert,
)
