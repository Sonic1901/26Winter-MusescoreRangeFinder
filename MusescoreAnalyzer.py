import os
import subprocess
import music21

# ==================================================================================
#                                 CONFIGURATION
# ==================================================================================

SCORES_DIR = r'C:\Users\sonic\OneDrive\Documents\MuseScore3\Scores\2026Spring'
MUSE_PATH = r'C:\Program Files\MuseScore 4\bin\MuseScore4.exe'

# ==================================================================================

MAIN_VOICES = {
    'Soprano':  ['soprano', 'sop'],
    'Mezzo':    ['mezzo', 'mzs'],
    'Alto':     ['alto'],
    'Tenor':    ['tenor'],
    'Baritone': ['baritone', 'bari', 'bar'],
    'Bass':     ['bass']
}

SPLIT_KEYWORDS = {
    '1': ['1', 'i', 'one', 'first'],
    '2': ['2', 'ii', 'two', 'second']
}

def ensure_musicxml_exists():
    if not os.path.exists(SCORES_DIR):
        print(f"ERROR: Folder not found: {SCORES_DIR}")
        return False
    if not os.path.exists(MUSE_PATH):
        print(f"ERROR: MuseScore executable not found at: {MUSE_PATH}")
        return False

    mscz_files = [f for f in os.listdir(SCORES_DIR) if f.endswith('.mscz')]
    if not mscz_files:
        print("No .mscz files found to check.")
        return True

    print(f"Checking {len(mscz_files)} files for conversion...")
    conversions_needed = []
    
    for filename in mscz_files:
        base_name = os.path.splitext(filename)[0]
        xml_path = os.path.join(SCORES_DIR, base_name + ".musicxml")
        if not os.path.exists(xml_path):
            conversions_needed.append(filename)

    if not conversions_needed:
        print(" -> All files already converted.\n")
        return True

    print(f" -> Found {len(conversions_needed)} new files to convert. Launching MuseScore...\n")
    for filename in conversions_needed:
        input_path = os.path.join(SCORES_DIR, filename)
        output_path = os.path.join(SCORES_DIR, os.path.splitext(filename)[0] + ".musicxml")
        print(f"    Converting: {filename} ...")
        try:
            subprocess.run([MUSE_PATH, input_path, "-o", output_path], check=True)
        except subprocess.CalledProcessError as e:
            print(f"    ERROR converting {filename}: {e}")
            
    print("\nConversion complete. Starting Analysis...\n")
    return True

def get_voice_classification(part_name_clean):
    main_cat = None
    for category, keywords in MAIN_VOICES.items():
        if any(k in part_name_clean for k in keywords):
            main_cat = category
            break
    if not main_cat:
        return None, None

    sub_cat = 'Generic'
    if any(k in part_name_clean for k in SPLIT_KEYWORDS['1']):
        sub_cat = '1'
    elif any(k in part_name_clean for k in SPLIT_KEYWORDS['2']):
        sub_cat = '2'
        
    return main_cat, sub_cat

def clean_filename(fname):
    return os.path.splitext(fname)[0]

def calculate_dynamic_duration(score):
    """Calculates total duration in seconds accounting for tempo changes."""
    try:
        # Get all tempo marks, flattened, with absolute offsets
        tempos = list(score.flat.getElementsByClass(music21.tempo.MetronomeMark))
        total_q_len = float(score.highestTime) # Total quarter notes in the score
        
        # If no tempo changes, fall back to default 120 BPM
        if not tempos:
            return (total_q_len / 120.0) * 60.0
            
        # Ensure tempos are sorted by their absolute offset in the piece
        tempos.sort(key=lambda t: t.offset)
        
        # Flattening pieces merges multiple parts, which can duplicate tempo markings at the same offset.
        unique_tempos = []
        for t in tempos:
            if not unique_tempos or t.offset > unique_tempos[-1].offset:
                unique_tempos.append(t)
            else:
                # If tempos exist at the same offset, just keep one
                unique_tempos[-1] = t
                
        tempos = unique_tempos
        total_seconds = 0.0
        
        # If the first tempo mark isn't at offset 0, assume 120 BPM for the intro
        if tempos[0].offset > 0:
            initial_q_len = float(tempos[0].offset)
            total_seconds += (initial_q_len / 120.0) * 60.0
            
        # Calculate time spent in each tempo block
        for i in range(len(tempos)):
            bpm = tempos[i].getQuarterBPM()
            start_offset = float(tempos[i].offset)
            
            # The block ends at the next tempo change, or the end of the song
            if i + 1 < len(tempos):
                end_offset = float(tempos[i+1].offset)
            else:
                end_offset = total_q_len
                
            q_len = end_offset - start_offset
            
            if q_len > 0:
                total_seconds += (q_len / bpm) * 60.0
                
        return total_seconds
    except Exception as e:
        print(f"    Error calculating dynamic duration: {e}")
        return 0.0

def process_complete():
    if not ensure_musicxml_exists():
        return

    stats = {}
    for v in MAIN_VOICES:
        stats[v] = {
            'overall': {'min': 127, 'max': 0, 'max_span': -1, 'span_notes': (0,0), 'span_song': ""},
            '1':       {'min': 127, 'max': 0, 'max_span': -1, 'span_notes': (0,0), 'span_song': ""},
            '2':       {'min': 127, 'max': 0, 'max_span': -1, 'span_notes': (0,0), 'span_song': ""},
            'Generic': {'min': 127, 'max': 0, 'max_span': -1, 'span_notes': (0,0), 'span_song': ""}
        }

    song_lengths = {}

    files = [f for f in os.listdir(SCORES_DIR) if f.endswith(('.musicxml', '.xml', '.mxl'))]
    print(f"Found {len(files)} XML files. Analyzing notes and dynamic durations...")

    for filename in files:
        path = os.path.join(SCORES_DIR, filename)
        try:
            score = music21.converter.parse(path)
            
            # --- Dynamic Song Length Calculation ---
            total_seconds = calculate_dynamic_duration(score)
            if total_seconds > 0:
                mins = int(total_seconds // 60)
                secs = int(total_seconds % 60)
                song_lengths[clean_filename(filename)] = f"{mins}:{secs:02d}"
            else:
                song_lengths[clean_filename(filename)] = "N/A"
            # ---------------------------------------

            for part in score.parts:
                raw_name = (part.partName or part.partAbbreviation or "").lower()
                clean_name = raw_name.replace('.', ' ').replace('-', ' ')
                
                main_cat, sub_cat = get_voice_classification(clean_name)
                
                if main_cat:
                    pitches = []
                    for element in part.recurse().notes:
                        if element.isNote:
                            pitches.append(element.pitch.ps)
                        elif element.isChord:
                            for p in element.pitches:
                                pitches.append(p.ps)
                    
                    if pitches:
                        p_min, p_max = min(pitches), max(pitches)
                        span = p_max - p_min
                        
                        def update_stat_block(block, p_min, p_max, span, filename):
                            if p_min < block['min']: block['min'] = p_min
                            if p_max > block['max']: block['max'] = p_max
                            if span > block['max_span']:
                                block['max_span'] = span
                                block['span_notes'] = (p_min, p_max)
                                block['span_song'] = filename

                        update_stat_block(stats[main_cat][sub_cat], p_min, p_max, span, filename)
                        update_stat_block(stats[main_cat]['overall'], p_min, p_max, span, filename)
                            
        except Exception as e:
            print(f"Skipping {filename}: {e}")

    # Output Configuration
    COL_VOICE = 16
    COL_RANGE = 22
    PREFIX_LEN = COL_VOICE + 3 + COL_RANGE + 3
    max_line_len = PREFIX_LEN + len("MAX SPAN (SINGLE SONG)")
    
    def generate_row_strings(data_block, label):
        if data_block['max_span'] == -1: return None
        d = data_block
        min_n = music21.pitch.Pitch(ps=d['min']).nameWithOctave
        max_n = music21.pitch.Pitch(ps=d['max']).nameWithOctave
        semitones = int(d['max'] - d['min'])
        range_str = f"{min_n} - {max_n} ({semitones} st)"
        span_low = music21.pitch.Pitch(ps=d['span_notes'][0]).nameWithOctave
        span_high = music21.pitch.Pitch(ps=d['span_notes'][1]).nameWithOctave
        song_display = clean_filename(d['span_song'])
        span_str = f"{span_low} to {span_high} ({int(d['max_span'])} st) in {song_display}"
        return f"{label:<{COL_VOICE}} | {range_str:<{COL_RANGE}} | {span_str}"

    # Calculate Widths & Check for Redundancy
    for voice in MAIN_VOICES:
        cat_data = stats[voice]
        
        active_subs = 0
        if cat_data['1']['max_span'] != -1: active_subs += 1
        if cat_data['2']['max_span'] != -1: active_subs += 1
        
        cat_data['hide_subs'] = (active_subs < 2)

        row = generate_row_strings(cat_data['overall'], voice.upper())
        if row: max_line_len = max(max_line_len, len(row))
        
        if not cat_data['hide_subs']:
            sub_labels = [('1', '   Slope 1'), ('2', '   Slope 2')]
            for key, label in sub_labels:
                label_fixed = label.replace("Slope", voice) 
                row = generate_row_strings(cat_data[key], label_fixed)
                if row: max_line_len = max(max_line_len, len(row))

    # Print Range Output
    separator = "=" * max_line_len
    divider = "-" * max_line_len
    
    print("\n" + separator)
    header = f"{'VOICE PART':<{COL_VOICE}} | {'OVERALL RANGE':<{COL_RANGE}} | {'MAX SPAN (SINGLE SONG)'}"
    print(header)
    print(divider)
    
    for voice in ['Soprano', 'Mezzo', 'Alto', 'Tenor', 'Baritone', 'Bass']:
        cat_data = stats[voice]
        main_row = generate_row_strings(cat_data['overall'], voice.upper())
        
        if main_row:
            print(main_row)
            if not cat_data.get('hide_subs', False):
                sub_labels = [('1', '   Slope 1'), ('2', '   Slope 2')]
                for key, label in sub_labels:
                    label_fixed = label.replace("Slope", voice) 
                    sub_row = generate_row_strings(cat_data[key], label_fixed)
                    if sub_row:
                        print(sub_row)
            print(divider)
            
    print(" * st = semitone")

    # Print Song Durations Output
    if song_lengths:
        duration_separator = "=" * 45
        print("\n\n" + duration_separator)
        print(f"{'SONG TITLE':<30} | {'DURATION'}")
        print("-" * 45)
        for song, duration in sorted(song_lengths.items()):
            print(f"{song:<30} | {duration}")
        print(duration_separator + "\n")

if __name__ == "__main__":
    process_complete()