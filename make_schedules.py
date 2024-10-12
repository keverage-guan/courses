import pandas as pd
import itertools
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
import ast
import seaborn as sns
import os
import datetime

pd.options.mode.chained_assignment = None

class ScheduleMaker:
    def __init__(self, schedules, num_courses=6, must_haves=[], at_least=[], must_select=[], at_most=[], exclude=[], unique_deps=True, day_limits=dict(), time_limits=[]):
        if isinstance(schedules, str):
            self.schedules = pd.read_excel(schedules)
        elif isinstance(schedules, pd.DataFrame):
            self.schedules = schedules
        else:
            raise ValueError("schedules is not a valid df or xlsx filepath")

        self.schedules['Days'] = self.schedules['Days'].apply(ast.literal_eval)

        self.courses = []
        for department, course in set(zip(self.schedules["Department"], self.schedules["Course"])):
            self.courses.append({'Department': department, 'Course': course})

        self.params = {
            'num_courses': num_courses,
            'must_haves': must_haves,
            'at_least': at_least,
            'must_select': must_select,
            'at_most': at_most,
            'exclude': exclude,
            'uniqueDeps': unique_deps,
            'day_limits': day_limits,
            'time_limits': time_limits
        }

        self.results = None

    def update_param(self, param, value):
        self.params[param] = value

    def __overlap(self, row, new_times):
        if (any([day in row['Days'] for day in new_times['Days']]) and (row['End'] >= new_times['Start']) and (row['Start'] <= new_times['End'])):
            return True
        return False

    def __addable(self, existing_times, new_times):
        # check time limits
        time_limits = self.params['time_limits'].copy()
        for index, time_limit in enumerate(time_limits):
            start = datetime.datetime.strptime(time_limit[0], '%I:%M %p')
            end = datetime.datetime.strptime(time_limit[1], '%I:%M %p')
            time_limits[index] = (start, end)

        start = datetime.datetime.strptime(new_times['Start'], '%H:%M:%S')
        end = datetime.datetime.strptime(new_times['End'], '%H:%M:%S')

        if any([(start < time_limit[1] and end > time_limit[0]) for time_limit in time_limits]):
            return False

        # check overlaps
        for row in existing_times:
            if self.__overlap(row, new_times):
                return False

        return True

    def __generate_combos(self):
        courses = self.courses.copy()

        # don't have these
        for excluded in self.params['exclude']:
            courses = [course for course in courses if not (course['Department'] == excluded or course['Department'] + str(course['Course']) == excluded)]

        combos = list(itertools.combinations(courses, self.params['num_courses']))

        print(f"Generated {len(combos)} combinations")

        # have all of these
        for must_have in self.params['must_haves']:
            combos = [combo for combo in combos if any((must_have in (course['Department'] + str(course['Course']))) for course in combo)]

        print(f"Filtered to {len(combos)} combinations with all must haves")

        # have at least some number of these
        for least in self.params['at_least']:
            combos = [combo for combo in combos if sum(any(e in (course['Department'] + str(course['Course'])) for e in least['Courses']) for course in combo) >= least['Number']]

        print(f"Filtered to {len(combos)} combinations with at least all at leasts")

        # have at most some number of these
        for most in self.params['at_most']:
            combos = [combo for combo in combos if sum(any(e in (course['Department'] + str(course['Course'])) for e in most['Courses']) for course in combo) <= most['Number']]

        print(f"Filtered to {len(combos)} combinations with at most all at mosts")

        # have some number of these
        for select in self.params['must_select']:
            combos = [combo for combo in combos if sum(any(e in (course['Department'] + str(course['Course'])) for e in select['Courses']) for course in combo) == select['Number']]

        print(f"Filtered to {len(combos)} combinations with all must selects")

        return combos

    def __exceed_days(self, schedule):
        counter = dict()
        for class_ in schedule:
            for day in class_['Days']:
                counter[day] = counter.get(day, 0) + 1

        for limited_day in self.params['day_limits'].keys():
            if limited_day in counter.keys() and counter[limited_day] > self.params['day_limits'][limited_day]:
                return True

        return False

    def __find_combination(self, schedule, keys, current_schedule):
        key = keys[0]

        # get rows of schedule where Key is key as a df called key_df
        key_df = schedule[schedule['Key'] == key]

        # iterate through rows of key_df
        for index, row in key_df.iterrows():
            # check if row overlaps with any rows in current_schedule
            if self.__addable(current_schedule, row):
                # if not, add row to current_schedule
                new_schedule = current_schedule.copy()
                new_schedule.append(row)
                # if keys is empty, return current_schedule
                if len(keys) == 1:
                    # check day limit
                    if not self.__exceed_days(new_schedule):
                        self.results.append(pd.concat(new_schedule, axis=1).T.reset_index(drop=True))
                        return True
                    continue
                # else, call find_combination with keys[1:], current_schedule
                else:
                    if self.__find_combination(schedule, keys[1:], new_schedule):
                        return True
        return False

    def generate_schedules(self):
        self.results = []

        self.schedules['Key'] = self.schedules['Department'] + self.schedules['Course'].astype(str)

        combos = self.__generate_combos()

        print("Filtering time and date restrictions...")

        num_combos = len(combos)

        for combo in combos:
            courses = pd.DataFrame(list(combo))
            courses["Key"] = courses['Department'] + courses['Course'].astype(str)

            schedule = self.schedules[self.schedules['Key'].isin(courses['Key'])]

            if (len(courses['Key'].unique()) != self.params['num_courses']):
                continue

            schedule['Section'] = schedule['Section'].str[0]
            schedule['Key'] = schedule['Department'] + schedule['Course'].astype(str) + schedule['Section']
            schedule.drop(columns=['Department', 'Course', 'Section'], inplace=True)

            key_counts = schedule['Key'].value_counts().reset_index()
            key_counts.columns = ['Key', 'Count']
            schedule = schedule.merge(key_counts, on='Key')
            schedule = schedule.sort_values(by=['Count'])
            keys = schedule['Key'].unique()

            attempt = self.__find_combination(schedule, keys, [])

            if not attempt:
                num_combos -= 1
                if num_combos % 100 == 0:
                    print(f"{num_combos} combinations remaining")

        return len(self.results)

    def __get_text_dimensions(self, text_string, font):
        # https://stackoverflow.com/a/46220683/9263761
        ascent, descent = font.getmetrics()

        text_width = font.getmask(text_string).getbbox()[2]
        text_height = font.getmask(text_string).getbbox()[3] + descent

        return text_width, text_height

    def __draw_schedule(self, schedule, filepath):
        # Convert start and end times to datetime objects
        # schedule['Start'] = pd.to_datetime(schedule['Start'])
        # schedule['End'] = pd.to_datetime(schedule['End'])

        #specify format 
        schedule['Start'] = pd.to_datetime(schedule['Start'], format='%H:%M:%S')
        schedule['End'] = pd.to_datetime(schedule['End'], format='%H:%M:%S')

        # generate a list of pastel colors
        classes = [x[:-1] for x in list(schedule['Key'].unique())]
        palette = sns.color_palette('pastel', len(classes)).as_hex()

        colors = {}
        for j, c in enumerate(classes):
            colors[c] = palette[j]

        # Create a blank image with the desired size
        width = 3000
        height = 2400
        image = Image.new('RGB', (width + 1, height), 'white')
        draw = ImageDraw.Draw(image)

        time_font = ImageFont.truetype('arial.ttf', 40)
        day_font = ImageFont.truetype('arial.ttf', 60)
        class_font = ImageFont.truetype('arial.ttf', 36)
        legend_font = ImageFont.truetype('arial.ttf', 48)

        # Define the width and height of each time slot
        time_slot_width = width // 5
        time_slot_height = height // 24

        # Draw day labels on top
        for day_idx, day in enumerate(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']):
            text_width, text_height = self.__get_text_dimensions(day, font=day_font)
            x = day_idx * time_slot_width + (time_slot_width - text_width) // 2
            y = 5  # Some padding
            draw.text((x, y), day, font=day_font, fill='black')

        # Draw the time slots for each day and draw time labels on the left
        for day_idx, day in enumerate(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']):
            for hour in range(24):
                top_left = (day_idx * time_slot_width, hour * time_slot_height)
                bottom_right = ((day_idx + 1) * time_slot_width, (hour + 1) * time_slot_height)
                draw.rectangle([top_left, bottom_right], outline='black')

        # Draw the course schedule
        for idx, row in schedule.iterrows():
            key = row['Key']
            name = row['Name']
            days = row['Days']
            start_hour = row['Start'].hour
            start_minute = row['Start'].minute
            end_hour = row['End'].hour
            end_minute = row['End'].minute
            color = colors[key[:-1]]

            for day in days:
                day_idx = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'].index(day)
                top_left = (day_idx * time_slot_width, start_hour * time_slot_height + (start_minute / 60) * time_slot_height)
                bottom_right = (day_idx * time_slot_width + time_slot_width, end_hour * time_slot_height + (end_minute / 60) * time_slot_height)
                draw.rectangle([top_left, bottom_right], fill=color)

                # Draw class labels (Key)
                class_label = f"{key} ({start_hour:02}:{start_minute:02} - {end_hour:02}:{end_minute:02})"
                text_width, text_height = self.__get_text_dimensions(class_label, font=class_font)
                x = day_idx * time_slot_width + (time_slot_width - text_width) // 2
                y = start_hour * time_slot_height + (start_minute / 60) * time_slot_height + (time_slot_height - text_height) // 2
                draw.text((x, y), class_label, font=class_font, fill='black')

        max_name_length = 0
        texts = []

        # Create a list of all keys and names
        key_name_pairs = {}
        for idx, row in schedule.iterrows():
            key = row['Key'][:6]
            name = row['Name']
            key_name_pairs[key]=name

        for idx, key in enumerate(key_name_pairs.keys()):
            text = f"{key} - {key_name_pairs[key]}"
            # for each text, if there are more than 15 characters, look for a space after 15 characters and split into two lines
            for line in range(len(text) // 20):
                for i in range(20*(line+1), len(text)):
                    if text[i] == ' ':
                        text = text[:i] + '\n' + text[i+1:]
                        break
            # trim text of white space at beginning and end
            text = text.strip()     
            longest_line = max(text.split('\n'), key=len)
            text_width, text_height = self.__get_text_dimensions(longest_line, font=class_font)
            texts.append(text)
            if text_width > max_name_length:
                max_name_length = text_width

        extra_width = int(width * 0.05 + max_name_length*1.2)

        # Create a new image with added blank space on the left
        new_width = width + extra_width
        new_image = Image.new('RGB', (new_width, height), 'white')
        # Paste the original image onto the new image, shifted to the right
        new_image.paste(image, (int(width*0.05), 0))
        image = new_image
        draw = ImageDraw.Draw(image)

        for hour in range(24):
            text = f'{hour:02}:00'
            text_width, text_height = self.__get_text_dimensions(text, font=time_font)
            x = 5  # Some padding
            y = hour * time_slot_height + (time_slot_height - text_height) // 2
            draw.text((x, y), text, font=time_font, fill='black')
       

        # Draw the texts on the right
        for idx, text in enumerate(texts):
            text_width, text_height = self.__get_text_dimensions(text, font=legend_font)
            x = int(width * 1.05 + max_name_length*0.1)
            y = (idx*1.5+7) * time_slot_height + (time_slot_height - text_height) // 2
            draw.text((x, y), text, font=class_font, fill='black')

        image.save(filepath)

    def draw_schedules(self):
        if len(self.results) != 0:
            current_datetime = datetime.datetime.now()
            formatted_datetime = current_datetime.strftime("%d_%m_%y_%H_%M_%S")
            directory_name = f"schedules_{formatted_datetime}"

            # Create the directory in the current working directory
            try:
                os.mkdir(directory_name)
                print(f"Directory '{directory_name}' created successfully.")
            except OSError:
                print(f"Creation of directory '{directory_name}' failed.")

            for i, result in enumerate(self.results):
                schedule = result
                filename = f"course_schedule{i}.png"
                image_path = os.path.join(directory_name, filename)
                self.__draw_schedule(schedule, image_path)

            # Write the dictionary to a text file
            params_filename = "params.txt"
            params_file_path = os.path.join(directory_name, params_filename)

            with open(params_file_path, "w") as params_file:
                for key, value in self.params.items():
                    params_file.write(f"{key}: {value}\n")

            print('Schedules generated')

        else:
            print('No results')

        
