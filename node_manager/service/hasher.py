import hashlib


def file_hash(filepath):
    try:
        with open(filepath, "rb") as f:  # Open in binary mode
            sha256_hash = hashlib.sha256()
            while True:
                chunk = f.read(4096)  # Read in chunks to handle large files
                if not chunk:
                    break
                sha256_hash.update(chunk)
            return sha256_hash.hexdigest()
    except Exception as e:
        print(f"Error processing file '{filepath}': {e}")