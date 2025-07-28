from PIL import Image, ImageDraw

# Create a blank white image
img = Image.new("RGB", (120, 120), "white")
draw = ImageDraw.Draw(img)

# Draw the bulb (circle)
draw.ellipse((30, 10, 90, 70), fill="#ffe066", outline="#ffd700", width=3)

# Draw the base (rectangle)
draw.rectangle((50, 70, 70, 100), fill="#cccccc", outline="#888888", width=2)

# Draw the filament (line)
draw.line((60, 40, 60, 70), fill="#ffae00", width=3)
draw.arc((50, 50, 70, 70), start=0, end=180, fill="#ffae00", width=2)

# Draw screw lines on the base
for y in range(75, 100, 6):
    draw.line((52, y, 68, y), fill="#888888", width=1)

# Save as mimo.jpg
img.save("mimo.jpg", "JPEG")
print("Lightbulb icon generated as mimo.jpg")
