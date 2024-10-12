import requests
from bs4 import BeautifulSoup
import pandas as pd
import re

class CourseInfoScraper:
    def __init__(self, classes_df, schedules_df=None):
        if isinstance(classes_df, str):
            try:
                self.classes_df = pd.read_excel('classes.xlsx')
            except:
                raise ValueError("Invalid filepath")
        elif isinstance(classes_df, pd.DataFrame):
            self.classes_df = classes_df
        else:
            raise ValueError("Must pass in dataframe or filepath to excel data for classes_df")

        if schedules_df is None:
            self.schedules_df = pd.DataFrame(columns=['Department', 'Course', 'Section', 'Days', 'Start', 'End'])
        elif isinstance(schedules_df, str):
            self.schedules_df = pd.read_excel('schedules.xlsx')
        elif isinstance(schedules_df, pd.DataFrame):
            self.schedules_df = schedules_df
        else:
            raise ValueError("schedules_df is not a valid df or xlsx filepath")

    def __parse_days(self, day_string):
        days = []

        # iterate through characters in day_string
        for i, char in enumerate(day_string):
            if char == 'M':
                days.append('Monday')
            elif char == 'T':
                if (i+1) == len(day_string) or day_string[i+1] != 'h':
                    days.append('Tuesday')
            elif char == 'W':
                days.append('Wednesday')
            elif char == 'h':
                days.append('Thursday')
            elif char == 'F':
                days.append('Friday')

        return days

    def __scrape_course(self, course):
       # if course looks like CHI108 or CHI 108, split into department and course
        if re.match(r'[A-Z]{3}\d{3}', course):
            department = course[:3]
            course = course[3:]
            search_URL = f"https://mobile.princeton.edu/default/courses/catalog?area={department}"

        else: 
            #replace spaces with %20, replace commas with %2C, replace slashes with %2F, and replace colons with %3A
            search = course.replace(' ', '%20').replace(',', '%2C').replace('/', '%2F').replace(':', '%3A')
            search_URL = f"https://mobile.princeton.edu/default/courses/search?filter={search}&search=Search"

        page = requests.get(search_URL)
        results = BeautifulSoup(page.content, "html.parser").find_all('li', class_='kgoui_object')
        course_URL = None

        for result in results:
            item_titles = result.find_all('span', class_="kgoui_list_item_title")

            if len(item_titles) <= 0:
                continue
            text = item_titles[0].contents[0]
            if str(course) in text:
                # look for first instance of three capital letters, space, numbers in continuous text and set to course
                course = re.search(r'[A-Z]{3} \d{3}', text).group(0)
                course_URL = f"https://m.princeton.edu{result.find_all('a')[0].get('href')}"
                # look for the first colon in the text, take everything after it, trim it, and set to topic
                topic = text[text.find(':')+1:].strip()
                break

        if course_URL is None:
            print(f'No results for {course}')
            return None

        page2 = requests.get(course_URL)
        results = BeautifulSoup(page2.content, 'html.parser').find(id='kgoui_Rcontent_I1_Rcontent_I0_Rsections')
        sections = results.find_all('div', class_='kgoui_object')

        section_info = []
        for section in sections:
            try:
                section_info.append({'Section': section.find('span', text=re.compile(r'Section')).text.replace('Section: ', ''),
                'Schedule': section.find('span', text=re.compile(r'Schedule')).text.replace('Schedule: ', '')})
            except:
                continue

        return [course, topic, section_info]

    def __format_classes_df(self, classes_df):
        if classes_df.empty:
            return None
        # split schedule column of classes_df into two by the first space and split times
        classes_df[['Day', 'Time']] = classes_df['Schedule'].str.split(' ', n=1, expand=True)
        classes_df = classes_df.drop(columns=['Schedule'])

        time_extract = classes_df['Time'].str.extract(r'(\d{2}:\d{2} [APM]{2})-(\d{2}:\d{2} [APM]{2})')
        classes_df['Start'] = pd.to_datetime(time_extract[0], format='%I:%M %p').dt.time
        classes_df['End'] = pd.to_datetime(time_extract[1], format='%I:%M %p').dt.time
        classes_df = classes_df.drop(columns=['Time'])

        classes_df['Days'] = classes_df['Day'].apply(self.__parse_days)
        classes_df.drop('Day', axis=1, inplace=True)

        # if a Class column is there
        if 'Class' in classes_df.columns:
            # split Class column into Department and Course columns on space
            classes_df[['Department','Course']] = classes_df['Class'].str.split(' ', n=1, expand=True)
            classes_df.drop(columns=['Class'], inplace=True)

        # change dtype of days to be a list of strings
        classes_df['Days'] = classes_df['Days'].astype(str)
        # change Course to be int64
        classes_df['Course'] = classes_df['Course'].astype('int64')
        # reorder classes_df to have same column order as schedules_df
        classes_df = classes_df[self.schedules_df.columns]

        return classes_df

    def scrape_course_info(self):
        schedule_info = {}

        existing_courses = []

        # get a list of each department and course concatenated from schedules_df indexwise
        for index, row in self.schedules_df.iterrows():
            existing_courses.append(f'{row["Department"]}{row["Course"]}')

        for index, row in self.classes_df.iterrows():
            course = row['Course']
            dep = row['Department']

            # if course is type int or consists of digits 
            if isinstance(course, int) or re.match(r'\d+', str(course)):
                course = f'{dep}{course}'

            print(course)

            if (course in existing_courses) or course in self.schedules_df['Name'].values:
                continue
                    
            result = self.__scrape_course(course)
            if result is not None:
                schedule_info[f'{result[0]}'] = [result[1], result[2]]
            else:
                continue

        new_classes_df = pd.DataFrame(columns=['Class', 'Name', 'Section', 'Schedule'])

        # for each key in schedule_info
        for key in schedule_info:
            row = [key]
            row.append(schedule_info[key][0])
            for item in schedule_info[key][1]:
                row.append(item['Section'])
                row.append(item['Schedule'])

                # append row to new_classes_df
                new_classes_df.loc[len(new_classes_df)] = row
                row = [key]
                row.append(schedule_info[key][0])

        new_classes_df = self.__format_classes_df(new_classes_df)

        if new_classes_df:
            self.schedules_df = pd.concat([self.schedules_df, new_classes_df], ignore_index=True)

    def save_schedules_df(self, filename='schedules.xlsx'):
        self.schedules_df.to_excel(filename, index=False)
