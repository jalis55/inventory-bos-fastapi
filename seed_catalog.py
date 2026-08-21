"""Seed a computer-accessories catalog (categories, brands, products, variants).

Idempotent: reuses existing categories/brands/products/variants by name/SKU.
Run: python seed_catalog.py
"""
import asyncio
import httpx
from app.utils.security import create_access_token

BASE = "http://127.0.0.1:8000"

# (category) -> list of (product name, description, [ (brand, [(variant_name, sku), ...]) ... ])
CATALOG = {
    "Storage": [
        ("SATA SSD", "2.5 inch SATA solid state drive", [
            ("samsung", [("240GB", "ssd-sam-240g"), ("480GB", "ssd-sam-480g"), ("1TB", "ssd-sam-1t")]),
            ("adata", [("240GB", "ssd-adt-240g"), ("480GB", "ssd-adt-480g"), ("1TB", "ssd-adt-1t")]),
        ]),
        ("M.2 NVMe SSD", "PCIe NVMe M.2 solid state drive", [
            ("samsung", [("256GB", "nvme-sam-256g"), ("512GB", "nvme-sam-512g"), ("1TB", "nvme-sam-1t")]),
            ("kingston", [("256GB", "nvme-kng-256g"), ("512GB", "nvme-kng-512g"), ("1TB", "nvme-kng-1t")]),
        ]),
        ("USB Flash Drive", "Portable USB flash drive", [
            ("transcend", [("16GB", "usb-trs-16g"), ("32GB", "usb-trs-32g"), ("64GB", "usb-trs-64g"), ("128GB", "usb-trs-128g")]),
            ("adata", [("32GB", "usb-adt-32g"), ("64GB", "usb-adt-64g")]),
        ]),
        ("SD Card", "Secure Digital memory card", [
            ("samsung", [("32GB", "sd-sam-32g"), ("64GB", "sd-sam-64g"), ("128GB", "sd-sam-128g")]),
        ]),
        ("External HDD", "Portable external hard disk", [
            ("adata", [("1TB", "hdd-adt-1t"), ("2TB", "hdd-adt-2t")]),
        ]),
    ],
    "Memory": [
        ("DDR4 RAM", "DDR4 desktop memory module", [
            ("corsair", [("8GB", "ram4-csr-8g"), ("16GB", "ram4-csr-16g"), ("32GB", "ram4-csr-32g")]),
            ("kingston", [("8GB", "ram4-kng-8g"), ("16GB", "ram4-kng-16g")]),
        ]),
        ("DDR5 RAM", "DDR5 desktop memory module", [
            ("corsair", [("8GB", "ram5-csr-8g"), ("16GB", "ram5-csr-16g"), ("32GB", "ram5-csr-32g")]),
        ]),
    ],
    "Keyboards": [
        ("Mechanical Keyboard", "RGB mechanical switch keyboard", [
            ("redragon", [("Black Red Switch", "kb-mech-red-blk"), ("White Red Switch", "kb-mech-red-wht"), ("Black Blue Switch", "kb-mech-blue-blk"), ("White Brown Switch", "kb-mech-brown-wht")]),
        ]),
        ("Keyboard Mouse Combo", "Wireless keyboard and mouse set", [
            ("logitech", [("Black", "kb-combo-blk"), ("White", "kb-combo-wht")]),
        ]),
    ],
    "Mice & Pointing": [
        ("Gaming Mouse", "RGB gaming optical mouse", [
            ("redragon", [("Black", "mouse-gm-blk"), ("White", "mouse-gm-wht"), ("Pink", "mouse-gm-pnk")]),
        ]),
        ("Wireless Mouse", "2.4G wireless optical mouse", [
            ("logitech", [("Black", "mouse-wl-blk"), ("White", "mouse-wl-wht"), ("Pink", "mouse-wl-pnk")]),
            ("techgear", [("Black", "mouse-wl-tg-blk"), ("Grey", "mouse-wl-tg-gry")]),
        ]),
        ("Optical Mouse", "Wired USB optical mouse", [
            ("techgear", [("Black", "mouse-opt-blk"), ("Red", "mouse-opt-red")]),
        ]),
    ],
    "Displays": [
        ("LED Monitor", "Full HD LED monitor", [
            ("asus", [("21.5 inch", "mon-led-asus-215"), ("24 inch", "mon-led-asus-24")]),
            ("benq", [("24 inch", "mon-led-bq-24"), ("27 inch", "mon-led-bq-27")]),
        ]),
        ("Portable Monitor", "USB-C portable display", [
            ("asus", [("15.6 inch", "mon-pt-asus-156")]),
        ]),
    ],
    "Cables & Adapters": [
        ("HDMI Cable", "High-speed HDMI cable", [
            ("techgear", [("1m", "hdmi-1m"), ("2m", "hdmi-2m"), ("3m", "hdmi-3m"), ("5m", "hdmi-5m")]),
        ]),
        ("LAN Cable Cat6", "Cat6 Ethernet patch cable", [
            ("tp-link", [("5m", "lan6-5m"), ("10m", "lan6-10m"), ("20m", "lan6-20m")]),
        ]),
        ("USB-C Cable", "USB-C to USB-A fast charge cable", [
            ("anker", [("1m", "usbc-1m"), ("2m", "usbc-2m")]),
        ]),
    ],
    "Audio": [
        ("Gaming Headset", "Wired gaming headset with mic", [
            ("redragon", [("Black", "head-gm-blk"), ("White", "head-gm-wht")]),
        ]),
        ("Bluetooth Speaker", "Portable wireless speaker", [
            ("jbl", [("Go (Black)", "spk-bl-go-blk"), ("Go (Blue)", "spk-bl-go-blu"), ("Flip (Black)", "spk-bl-flip-blk")]),
        ]),
    ],
    "Webcams": [
        ("Webcam HD", "USB web camera", [
            ("logitech", [("720p", "cam-hd-720"), ("1080p FHD", "cam-hd-1080")]),
        ]),
    ],
    "Networking": [
        ("Wi-Fi Router", "Dual band wireless router", [
            ("tp-link", [("Archer AC1200", "rtr-ac1200"), ("Archer AX1500", "rtr-ax1500")]),
        ]),
        ("Network Switch", "Gigabit unmanaged switch", [
            ("tp-link", [("5-Port", "swt-5p"), ("8-Port", "swt-8p")]),
        ]),
    ],
    "Power & Charging": [
        ("UPS", "Line-interactive uninterruptible power supply", [
            ("techgear", [("600VA", "ups-600va"), ("1000VA", "ups-1000va")]),
        ]),
        ("Laptop Adapter", "Laptop AC power adapter", [
            ("techgear", [("45W", "adapt-45w"), ("65W", "adapt-65w"), ("90W", "adapt-90w")]),
        ]),
    ],
    "Cooling": [
        ("CPU Cooler", "Tower CPU air cooler", [
            ("cooler-master", [("120mm RGB", "cool-rgb-120"), ("92mm", "cool-92")]),
        ]),
        ("Cooling Pad", "Laptop cooling pad", [
            ("techgear", [("14 inch", "coolpad-14"), ("17 inch", "coolpad-17")]),
        ]),
    ],
}

NEW_BRANDS = [
    "logitech", "kingston", "transcend", "corsair", "redragon",
    "techgear", "anker", "jbl", "benq", "tp-link", "cooler-master", "seagate",
]


async def list_all(client, path, limit=200):
    items, skip = [], 0
    while True:
        r = await client.get(path, params={"limit": limit, "skip": skip})
        r.raise_for_status()
        data = r.json()
        page = data if isinstance(data, list) else data.get("items", [])
        items.extend(page)
        total = data.get("total", len(page)) if isinstance(data, dict) else len(page)
        if not page or len(items) >= total:
            break
        skip += limit
    return items


async def main():
    token = create_access_token({"sub": "jalis@admin.com"})
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(base_url=BASE, headers=headers, timeout=30, follow_redirects=True) as c:
        cats = {x["name"]: int(x["id"]) for x in await list_all(c, "/category/")}
        brands = {x["name"]: int(x["id"]) for x in await list_all(c, "/brands/")}
        products = await list_all(c, "/products/")
        variants = await list_all(c, "/variants/")
        existing_skus = {v["sku"] for v in variants}
        # products: (name, brand_name, category_name) -> id
        prod_map = {
            (p["name"].lower(), p["brand"]["name"].lower(), p["category"]["name"].lower()): p["id"]
            for p in products
        }

        # categories
        for name in CATALOG:
            if name not in cats:
                r = await c.post("/category/create", json={"name": name})
                if r.status_code in (200, 201):
                    cats[name] = int(r.json()["id"])
                    print(f"category + {name}")
                else:
                    print("category fail:", name, r.status_code, r.text[:150])

        # brands
        for name in NEW_BRANDS:
            if name not in brands:
                r = await c.post("/brands/", json={"name": name})
                if r.status_code in (200, 201):
                    brands[name] = int(r.json()["id"])
                    print(f"brand + {name}")
                else:
                    print("brand fail:", name, r.status_code, r.text[:150])

        nc = nb = np_ = nv = 0
        for cat_name, items in CATALOG.items():
            cat_id = cats.get(cat_name)
            if cat_id is None:
                print("skip (no category):", cat_name)
                continue
            for pname, desc, brand_variants in items:
                for bname, vlist in brand_variants:
                    bname_l = bname.lower()
                    if bname_l not in brands:
                        r = await c.post("/brands/", json={"name": bname})
                        if r.status_code in (200, 201):
                            brands[bname_l] = int(r.json()["id"])
                            nb += 1
                        else:
                            print("brand fail:", bname, r.status_code, r.text[:150])
                            continue
                    bid = brands[bname_l]
                    key = (pname.lower(), bname_l, cat_name.lower())
                    pid = prod_map.get(key)
                    if pid is None:
                        r = await c.post("/products/", json={
                            "name": pname, "description": desc,
                            "category_id": cat_id, "brand_id": bid,
                        })
                        if r.status_code in (200, 201):
                            pid = r.json()["id"]
                            prod_map[key] = pid
                            np_ += 1
                            print(f"product + {bname} {pname}")
                        else:
                            print("product fail:", bname, pname, r.status_code, r.text[:200])
                            continue
                    for vname, sku in vlist:
                        if sku in existing_skus:
                            continue
                        r = await c.post(f"/products/{pid}/variants", json={
                            "sku": sku, "variant_name": vname,
                            "unit_of_measure": "pcs", "pack_size": 1,
                            "reorder_level": 5,
                        })
                        if r.status_code in (200, 201):
                            existing_skus.add(sku)
                            nv += 1
                            print(f"  variant + {bname} {pname} [{vname}] ({sku})")
                        else:
                            print("variant fail:", sku, r.status_code, r.text[:200])

        print(f"\nDONE: +{nc} cat, +{nb} brand, +{np_} product, +{nv} variant")


if __name__ == "__main__":
    asyncio.run(main())