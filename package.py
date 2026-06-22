import os
import shutil
import sys
import argparse

IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.avif', '.svg', '.gif')
VIDEO_EXTS = ('.mp4', '.avi', '.mkv', '.mov', '.webm')
PDF_EXTS = ('.pdf',)

def organize_media(dest_dir, source_dir="public"):
    images_dir = os.path.join(dest_dir, "images")
    videos_dir = os.path.join(dest_dir, "videos")
    pdf_dir = os.path.join(dest_dir, "pdf")
    others_dir = os.path.join(dest_dir, "others")

    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(videos_dir, exist_ok=True)
    os.makedirs(pdf_dir, exist_ok=True)
    os.makedirs(others_dir, exist_ok=True)

    if not os.path.exists(source_dir):
        print(f"Source folder '{source_dir}' does not exist.")
        return

    for item in os.listdir(source_dir):
        src_path = os.path.join(source_dir, item)
        if os.path.isfile(src_path):
            ext = os.path.splitext(item)[1].lower()
            if ext in IMAGE_EXTS:
                shutil.copy2(src_path, os.path.join(images_dir, item))
                print(f"Copied image {item} to {images_dir}")
            elif ext in VIDEO_EXTS:
                shutil.copy2(src_path, os.path.join(videos_dir, item))
                print(f"Copied video {item} to {videos_dir}")
            elif ext in PDF_EXTS:
                shutil.copy2(src_path, os.path.join(pdf_dir, item))
                print(f"Copied pdf {item} to {pdf_dir}")
            else:
                shutil.copy2(src_path, os.path.join(others_dir, item))
                print(f"Copied other file {item} to {others_dir}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=["windows", "macos"])
    parser.add_argument("--action", choices=["prepare-dmg", "zip-dmg"])
    args = parser.parse_args()

    if args.platform == "windows":
        pkg_dir = "GalleryX-Windows"
        if os.path.exists(pkg_dir):
            shutil.rmtree(pkg_dir)
        os.makedirs(pkg_dir)

        # Copy exe
        exe_src = os.path.join("dist", "gallery.exe")
        if not os.path.exists(exe_src):
            if os.path.exists(os.path.join("dist", "GalleryX.exe")):
                exe_src = os.path.join("dist", "GalleryX.exe")
            else:
                raise FileNotFoundError("Could not find gallery.exe or GalleryX.exe in dist/")

        # Create exe folder inside pkg_dir
        exe_dir = os.path.join(pkg_dir, "exe")
        os.makedirs(exe_dir, exist_ok=True)
        shutil.copy2(exe_src, os.path.join(exe_dir, os.path.basename(exe_src)))

        # Organize media folders inside the package
        organize_media(pkg_dir)

        # Zip it
        zip_output = os.path.join("dist", "GalleryX-Windows")
        shutil.make_archive(zip_output, "zip", root_dir=".", base_dir=pkg_dir)
        print(f"Created {zip_output}.zip successfully.")

    elif args.platform == "macos":
        if args.action == "prepare-dmg":
            dmg_root = "dmg-root"
            if os.path.exists(dmg_root):
                shutil.rmtree(dmg_root)
            os.makedirs(dmg_root)

            # Copy App Bundle
            app_src = os.path.join("dist", "GalleryX.app")
            if not os.path.exists(app_src):
                raise FileNotFoundError("Could not find GalleryX.app in dist/")
            
            if sys.platform == "darwin":
                os.system(f"ditto {app_src} {dmg_root}/GalleryX.app")
                os.system(f"xattr -cr {dmg_root}/GalleryX.app")
            else:
                shutil.copytree(app_src, os.path.join(dmg_root, "GalleryX.app"), symlinks=True)

            # Organize media folders inside the DMG root
            organize_media(dmg_root)
            print("Prepared dmg-root with GalleryX.app and media folders.")

        elif args.action == "zip-dmg":
            pkg_dir = "GalleryX-macOS"
            if os.path.exists(pkg_dir):
                shutil.rmtree(pkg_dir)
            os.makedirs(pkg_dir)

            # Copy DMG
            dmg_src = os.path.join("dist", "GalleryX.dmg")
            if not os.path.exists(dmg_src):
                raise FileNotFoundError("Could not find GalleryX.dmg in dist/")

            shutil.copy2(dmg_src, os.path.join(pkg_dir, "GalleryX.dmg"))

            # Organize media folders inside the zip package
            organize_media(pkg_dir)

            # Zip it
            zip_output = os.path.join("dist", "GalleryX-macOS")
            shutil.make_archive(zip_output, "zip", root_dir=".", base_dir=pkg_dir)
            print(f"Created {zip_output}.zip successfully.")

if __name__ == "__main__":
    main()
