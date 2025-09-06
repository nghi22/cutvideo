import os

def rename_images_to_numbers(folder_path):
    try:
        # Lấy danh sách file ảnh (lọc file ảnh có phần mở rộng hợp lệ)
        valid_exts = ['.jpg', '.jpeg', '.png', '.webp', '.bmp']
        image_files = [f for f in os.listdir(folder_path) if os.path.splitext(f)[1].lower() in valid_exts]

        # Sắp xếp để giữ thứ tự nhất quán
        image_files.sort()

        # Đổi tên từng ảnh
        for i, filename in enumerate(image_files, start=1):
            old_path = os.path.join(folder_path, filename)
            ext = os.path.splitext(filename)[1].lower()
            new_name = f"{i}{ext}"
            new_path = os.path.join(folder_path, new_name)

            os.rename(old_path, new_path)
            print(f"Đã đổi: {filename} ➜ {new_name}")

        print("✅ Đã hoàn tất đổi tên tất cả ảnh.")

    except Exception as e:
        print(f"❌ Lỗi xảy ra: {e}")

# === Cấu hình ===
folder_path = r"C:\Users\ADMIN\Documents\GemPhone thongTin\RegFB\Nu Da Xong"   # 👉 Ví dụ: "C:/Users/duy/Pictures/anh"

# === Gọi hàm xử lý ===
rename_images_to_numbers(folder_path)
