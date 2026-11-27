"""归一化区域选择：坐标始终相对各自 page size，不混用 source/rectified 像素。"""
from ._common import box_to_bbox


def normalize_rect(rect):
    if not isinstance(rect, (list, tuple)) or len(rect) != 4 \
            or any(isinstance(v, bool) or not isinstance(v, (int, float))
                   for v in rect):
        raise ValueError('region.rect 须为 [x0,y0,x1,y1] 归一化坐标')
    x0, y0, x1, y1 = [float(v) for v in rect]
    if not (0 <= x0 <= 1 and 0 <= y0 <= 1 and 0 <= x1 <= 1 and 0 <= y1 <= 1):
        raise ValueError('region.rect 坐标须在 0 到 1 之间')
    return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]


def page_size(page, space=None):
    page = page or {}
    space = space or page.get('space') or 'source'
    if space == 'rectified':
        return page.get('rectified_size')
    return page.get('size')


def norm_bbox(bbox, size):
    if not bbox or not isinstance(size, (list, tuple)) or len(size) < 2:
        return None
    w, h = size[:2]
    if not isinstance(w, (int, float)) or not isinstance(h, (int, float)) \
            or w <= 0 or h <= 0:
        return None
    return [bbox[0] / w, bbox[1] / h, bbox[2] / w, bbox[3] / h]


def in_region(bbox, size, region):
    if not region:
        return True
    rect = normalize_rect(region.get('rect')) if region.get('rect') else None
    if rect is None:
        raise ValueError('region.rect 不能为空')
    norm = norm_bbox(bbox, size)
    if norm is None:
        return False
    return norm[0] <= rect[2] and norm[2] >= rect[0] \
        and norm[1] <= rect[3] and norm[3] >= rect[1]


def item_in_region(raw_box, page, region):
    if not region:
        return True
    pg = page or {}
    if region.get('space') and region['space'] != (pg.get('space') or 'source'):
        return False
    bbox = box_to_bbox(raw_box)
    return in_region(bbox, page_size(pg), region)


def table_bbox(table, page_index=None):
    rects = []
    for row in (table or {}).get('cells') or []:
        for cell in row:
            if isinstance(cell, dict):
                if page_index is not None and cell.get('page') != page_index:
                    continue
                cell = cell.get('bbox')
            bbox = box_to_bbox(cell)
            if bbox:
                rects.append(bbox)
    if not rects:
        return None
    return [min(b[0] for b in rects), min(b[1] for b in rects),
            max(b[2] for b in rects), max(b[3] for b in rects)]


def table_in_region(table, page, page_default, region):
    if not region:
        return True
    if region.get('page') is not None:
        if page_default is not None and region['page'] != page_default:
            return False
    coord = (table or {}).get('coord') or {}
    space = coord.get('space') or (page or {}).get('space') or 'source'
    if region.get('space') and region['space'] != space:
        return False
    return in_region(table_bbox(table, region.get('page')),
                     page_size(page, space), region)
