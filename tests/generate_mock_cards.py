import os
from PIL import Image, ImageDraw, ImageFont

def create_card_1(output_dir):
    """
    Creates a standard clean business card: John Doe at CloudScale Solutions.
    """
    # Create image with white background
    width, height = 800, 450
    img = Image.new('RGB', (width, height), color='#FFFFFF')
    draw = ImageDraw.Draw(img)
    
    # Draw simple corporate blue accent line
    draw.rectangle([0, 0, 20, height], fill='#1e3a8a')
    
    # We use default font since custom fonts might not be installed on Windows
    # PIL's default font is very small, so we draw multiple lines with spacing
    # Using default font means we draw character by character or line by line
    # Alternatively, PIL has a basic font, but to make it larger we can use a built-in TrueType font on Windows,
    # like Arial. Windows always has Arial.ttf.
    try:
        font_name = ImageFont.truetype("arial.ttf", 36)
        font_sub = ImageFont.truetype("arial.ttf", 20)
        font_body = ImageFont.truetype("arial.ttf", 18)
    except IOError:
        font_name = font_sub = font_body = ImageFont.load_default()
        
    # Draw Text
    draw.text((60, 50), "John Doe", fill='#1e293b', font=font_name)
    draw.text((60, 95), "Senior Software Architect", fill='#64748b', font=font_sub)
    draw.text((60, 130), "CloudScale Solutions", fill='#0284c7', font=font_sub)
    
    # Separator
    draw.line([60, 170, 740, 170], fill='#cbd5e1', width=2)
    
    # Contact info
    draw.text((60, 200), "Phone: +1-555-0199", fill='#334155', font=font_body)
    draw.text((60, 235), "Email: john.doe@cloudscale.com", fill='#334155', font=font_body)
    draw.text((60, 270), "Website: www.cloudscale.com", fill='#334155', font=font_body)
    
    # Address
    address_lines = [
        "Address: 100 Innovation Way",
        "Suite 400, Boston, MA 02110"
    ]
    draw.text((60, 310), address_lines[0], fill='#334155', font=font_body)
    draw.text((60, 335), address_lines[1], fill='#334155', font=font_body)
    
    # Save
    out_path = os.path.join(output_dir, "sample_card_1.png")
    img.save(out_path)
    print(f"Generated standard card at: {out_path}")

def create_card_2(output_dir):
    """
    Creates a dark blue business card, and rotates it by 90 degrees to test deskewing.
    """
    width, height = 800, 450
    # Dark card
    img = Image.new('RGB', (width, height), color='#0f172a')
    draw = ImageDraw.Draw(img)
    
    # Gold accent badge
    draw.rectangle([760, 0, width, height], fill='#d97706')
    
    try:
        font_name = ImageFont.truetype("arial.ttf", 36)
        font_sub = ImageFont.truetype("arial.ttf", 20)
        font_body = ImageFont.truetype("arial.ttf", 18)
    except IOError:
        font_name = font_sub = font_body = ImageFont.load_default()
        
    # Draw Text (White/Gold/Silver)
    draw.text((60, 60), "SARAH JENKINS", fill='#f8fafc', font=font_name)
    draw.text((60, 105), "VP of Product Strategy", fill='#fbbf24', font=font_sub)
    draw.text((60, 140), "ApexTech Innovations Group", fill='#94a3b8', font=font_sub)
    
    draw.line([60, 180, 700, 180], fill='#475569', width=2)
    
    draw.text((60, 210), "Tel: (415) 555-4832", fill='#cbd5e1', font=font_body)
    draw.text((60, 245), "Email: s.jenkins@apextech.com", fill='#cbd5e1', font=font_body)
    draw.text((60, 280), "Web: apextech.com/strategy", fill='#cbd5e1', font=font_body)
    draw.text((60, 315), "Address: 500 Market St, San Francisco, CA 94104", fill='#cbd5e1', font=font_body)
    
    # Rotate by 90 degrees to test Tesseract OSD deskewing!
    rotated_img = img.rotate(90, expand=True)
    
    out_path = os.path.join(output_dir, "sample_card_2_rotated.png")
    rotated_img.save(out_path)
    print(f"Generated rotated card at: {out_path}")

def create_card_3(output_dir):
    """
    Creates a card with missing elements: Jane Smith (Freelancer), no Company, no Website.
    To test empty value parsing and validator corrections.
    """
    width, height = 800, 450
    img = Image.new('RGB', (width, height), color='#fafafa')
    draw = ImageDraw.Draw(img)
    
    try:
        font_name = ImageFont.truetype("arial.ttf", 34)
        font_sub = ImageFont.truetype("arial.ttf", 20)
        font_body = ImageFont.truetype("arial.ttf", 18)
    except IOError:
        font_name = font_sub = font_body = ImageFont.load_default()
        
    draw.text((80, 80), "Jane Smith", fill='#171717', font=font_name)
    draw.text((80, 125), "Independent Graphic Designer", fill='#737373', font=font_sub)
    # Notice: No Company name drawn!
    
    draw.line([80, 175, 720, 175], fill='#e5e5e5', width=1)
    
    draw.text((80, 210), "Mobile: +44 7911 123456", fill='#404040', font=font_body)
    draw.text((80, 250), "Email: smith_design@gmail.com", fill='#404040', font=font_body)
    # Notice: No Website drawn!
    
    draw.text((80, 290), "Address: Flat 4, 12 High Street, London, UK", fill='#404040', font=font_body)
    
    out_path = os.path.join(output_dir, "sample_card_3_missing.png")
    img.save(out_path)
    print(f"Generated card with missing fields at: {out_path}")

if __name__ == "__main__":
    out_dir = "sample_cards"
    os.makedirs(out_dir, exist_ok=True)
    create_card_1(out_dir)
    create_card_2(out_dir)
    create_card_3(out_dir)
