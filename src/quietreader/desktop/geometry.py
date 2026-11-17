def visible_bounds(bounds, screens):
    if not screens:
        screens = [(0, 0, 1280, 800)]
    x, y, width, height = bounds
    screen = next((s for s in screens if s[0] <= x < s[0] + s[2] and s[1] <= y < s[1] + s[3]), screens[0])
    sx, sy, sw, sh = screen
    width, height = min(max(380, width), sw), min(max(360, height), sh)
    if not (sx <= x <= sx + sw - width and sy <= y <= sy + sh - height):
        x, y = sx + (sw - width) // 2, sy + (sh - height) // 2
    return x, y, width, height
