from paddlex import list_models

all_models = list_models()
vl_candidates = [m for m in all_models if any(k in m.lower() for k in ["vl", "vlm", "ocr_vl", "doc_vlm", "got"])]

print(f"📋 共 {len(all_models)} 个可用模型")
print(f"🔍 VLM/OCR-VL 候选 ({len(vl_candidates)} 个):")
for m in sorted(vl_candidates):
    print(f"   • {m}")

if not vl_candidates:
    print("\n⚠️ 未找到任何 VLM 模型，可能原因:")
    print("   1. paddlex 版本过旧，请 pip install paddlex --upgrade")
    print("   2. 需要额外安装 VL 插件包")