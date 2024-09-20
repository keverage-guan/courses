import re
import requests
from bs4 import BeautifulSoup
course = 'Intensive Intermediate Chinese'


# if course looks like CHI108 or CHI 108, split into department and course
if re.match(r'[A-Z]{3}\d{3}', course):
    department = course[:3]
    course = course[3:]
    search_URL = f"https://mobile.princeton.edu/default/courses/catalog?area={department}"

else: 
    # split string by spaces and join with +
    search = '+'.join(course.split(' '))
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
        course_URL = f"https://m.princeton.edu{result.find_all('a')[0].get('href')}"
        break

print(course_URL)