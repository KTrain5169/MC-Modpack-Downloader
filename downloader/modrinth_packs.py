import requests
import shutil
import json
import hashlib
import threading
from pathlib import Path
from tkinter import messagebox


class ModrinthProcessor:
    def process(self, manifest_path, overrides_path, destination_folder, modpack_name, status_callback):
        destination_folder = Path(destination_folder) / modpack_name

        # this doesn't work lmao
        if destination_folder.exists():
            messagebox.showerror(
                "Error", f"The folder '{destination_folder}' already exists. Please delete it before trying again.")
            return

        destination_folder.mkdir(parents=True)
        status_callback(f"Created folder '{destination_folder}'.")

        # Process the overrides folder, if it exists and is not None
        if overrides_path and overrides_path.exists():
            for item in overrides_path.iterdir():
                target_path = destination_folder / item.name
                if item.is_dir():
                    if target_path.exists() and target_path.is_dir():
                        status_callback(
                            f"Merging contents into existing directory '{target_path}'.")
                        shutil.copytree(item, target_path, dirs_exist_ok=True)
                    else:
                        shutil.copytree(item, target_path)
                else:
                    shutil.copy2(item, target_path)
            status_callback("Overrides folder contents copied.")
            shutil.rmtree(overrides_path)
            status_callback("Overrides folder deleted.")

        # Process the Modrinth index file
        if manifest_path and manifest_path.exists():
            with open(manifest_path, 'r') as manifest_file:
                manifest = json.load(manifest_file)

            # Start a new thread for each file download and hash verification
            threads = []
            for file in manifest['files']:
                mod_url = file['downloads'][0]
                mod_path = file.get('path', 'mods')
                expected_sha1 = file.get('hashes', {}).get('sha1')
                expected_sha512 = file.get('hashes', {}).get('sha512')

                # Determine the target file path
                mod_file_path = destination_folder / mod_path

                # Ensure the folder for the file exists
                mod_file_path.parent.mkdir(parents=True, exist_ok=True)

                # Create and start a new thread for downloading and verifying the file
                thread = threading.Thread(
                    target=self.download_and_verify,
                    args=(mod_url, mod_file_path, expected_sha1,
                          expected_sha512, status_callback)
                )
                thread.start()
                threads.append(thread)

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            manifest_path.unlink()
            status_callback("Modrinth index file deleted.")

    def download_and_verify(self, mod_url, mod_file_path, expected_sha1, expected_sha512, status_callback):
        """Downloads the file and verifies its hash."""
        try:
            mod_response = requests.get(mod_url)
            if mod_response.status_code == 200:
                with open(mod_file_path, 'wb') as mod_file:
                    mod_file.write(mod_response.content)
                # Update status via callback
                status_callback(f"Downloaded {mod_file_path}.")

                # Verify the file hashes
                if not self.verify_hashes(mod_file_path, expected_sha1, expected_sha512):
                    status_callback(
                        f"Hash mismatch for {mod_file_path}! Expected SHA-1: {expected_sha1}, SHA-512: {expected_sha512}.")
                else:
                    status_callback(f"Verified hashes for {mod_file_path}.")
            else:
                status_callback(
                    f"Failed to download {mod_file_path}: {mod_response.status_code}")
        except Exception as e:
            status_callback(f"Error downloading {mod_file_path}: {e}")

    def verify_hashes(self, file_path, expected_sha1, expected_sha512):
        """Verifies the SHA-1 and SHA-512 hashes of the downloaded file against expected values."""
        hash_sha1 = hashlib.sha1()
        hash_sha512 = hashlib.sha512()

        # Read the file in chunks to avoid memory issues with large files
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha1.update(chunk)
                hash_sha512.update(chunk)

        # Calculate the file's hashes
        file_sha1 = hash_sha1.hexdigest()
        file_sha512 = hash_sha512.hexdigest()

        # Compare the calculated hashes with the expected ones
        return (file_sha1 == expected_sha1) and (file_sha512 == expected_sha512)
