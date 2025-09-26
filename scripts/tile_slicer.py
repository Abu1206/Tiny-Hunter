from PIL import Image
import os


def slice_and_resize_strip(
    image_path, tile_width, tile_height, output_size, output_folder
):
    """
    Slices a horizontal image strip, resizes each tile, and saves them
    with zero-padded index filenames.

    Args:
        image_path (str): The path to the input image strip.
        tile_width (int): The width of a single tile in the original strip.
        tile_height (int): The height of a single tile in the original strip.
        output_size (tuple): A tuple (width, height) for the resized output tiles.
        output_folder (str): The name of the directory to save the output tiles.
    """
    # --- 1. Validate Input and Open Image ---
    try:
        img = Image.open(image_path)
    except FileNotFoundError:
        print(f"Error: The file '{image_path}' was not found.")
        return

    # Check for the correct resampling filter attribute based on Pillow version
    try:
        # Pillow 9.1.0+
        resample_filter = Image.Resampling.NEAREST
    except AttributeError:
        # Older Pillow versions
        resample_filter = Image.NEAREST

    total_width, image_height = img.size

    # --- 2. Check Dimensions ---
    if image_height != tile_height:
        print(
            f"Warning: Image height ({image_height}px) does not match the provided tile height ({tile_height}px)."
        )

    if total_width % tile_width != 0:
        print(
            f"Warning: Image width ({total_width}px) is not a perfect multiple of the tile width ({tile_width}px)."
        )

    # --- 3. Create Output Directory ---
    os.makedirs(output_folder, exist_ok=True)
    print(f"Output directory '{output_folder}' is ready.")

    # --- 4. Loop, Crop, Resize, and Save Tiles ---
    num_tiles = total_width // tile_width

    for i in range(num_tiles):
        # Define coordinates and crop the original tile
        left = i * tile_width
        top = 0
        right = left + tile_width
        bottom = tile_height
        tile = img.crop((left, top, right, bottom))

        # --- RESIZE THE CROPPED TILE ---
        # We use NEAREST filter to maintain the sharp pixel art look
        resized_tile = tile.resize(output_size, resample=resample_filter)

        # Create a zero-padded filename (e.g., 00.png, 01.png)
        filename = f"{str(i).zfill(2)}.png"
        output_path = os.path.join(output_folder, filename)

        # Save the RESIZED tile
        resized_tile.save(output_path, "PNG")
        print(f"Saved resized tile: {output_path}")

    print(
        f"\nSlicing and resizing complete! {num_tiles} tiles were successfully processed."
    )


# ==============================================================================
# --- HOW TO USE: Configure the variables below and run the script ---
# ==============================================================================
if __name__ == "__main__":
    # 1. Path to your exported horizontal image strip.
    INPUT_IMAGE_FILE = "0.png"

    # 2. Dimensions (in pixels) of a SINGLE tile in your ORIGINAL image strip.
    ORIGINAL_TILE_WIDTH = 32
    ORIGINAL_TILE_HEIGHT = 32

    # 3. The desired final dimensions (in pixels) for EACH output tile.
    OUTPUT_TILE_WIDTH = 16
    OUTPUT_TILE_HEIGHT = 16

    # 4. Name of the folder where the resized tiles will be saved.
    OUTPUT_FOLDER = "output_tiles_16x16"

    # Run the function with your settings
    slice_and_resize_strip(
        image_path=INPUT_IMAGE_FILE,
        tile_width=ORIGINAL_TILE_WIDTH,
        tile_height=ORIGINAL_TILE_HEIGHT,
        output_size=(OUTPUT_TILE_WIDTH, OUTPUT_TILE_HEIGHT),
        output_folder=OUTPUT_FOLDER,
    )
