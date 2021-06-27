import os
import json
from slugify import slugify
from urllib.parse import urlparse, urljoin


SRC = os.getcwd()
HOME = os.path.dirname(SRC)


def makeDirIfNotExists(path):
    """
        Make directory if not exists
        Args:
            - path (str): location of folder
    """
    if not os.path.exists(path):
        os.makedirs(path)


class Pharmacy:

    def __init__(self, **kwargs):
        self._id = kwargs.get('_id')
        self.name = kwargs.get('name')
        self.street = kwargs.get('street')
        self.zip_code = kwargs.get('zip_code')
        self.city = kwargs.get('city')
        self.slug_name = self.get_slug_name()
        self.folder_path = self.get_folder_path()
        self.overview_path = self.get_overview_path()
        self.subpages_path = self.get_subpages_path()
        self.overview_file = self.get_overview_file()

    def get_slug_name(self):
        return f"{slugify(self.name)}-{slugify(self.city)}" # create slug for pharmacy identifier

    def get_folder_path(self):
        path = os.path.join(HOME, "output", self.slug_name)
        makeDirIfNotExists(path)
        return path

    def get_overview_path(self):
        path = os.path.join(self.folder_path, "overview")
        makeDirIfNotExists(path)
        return path

    def get_subpages_path(self):
        subpage = os.path.join(self.folder_path, "subpages")
        makeDirIfNotExists(subpage)
        return subpage

    def get_overview_file(self):
        return os.path.join(self.overview_path, self.slug_name + ".json")

    def create_dict(self):
        return {
            "_id": self._id,
            "name": self.name,
            "street": self.street,
            "zip": self.zip_code,
            "city": self.city,
            "suggestions": []
        }

    def create_pharmacy_data(self, **kwargs):
        suggestions = kwargs.get('suggestions', [])

        data = self.create_dict()
        data['suggestions'] = suggestions

        makeDirIfNotExists(self.overview_path)

        with open(self.overview_file, 'w', encoding='utf-8') as fn:
            json.dump(data, fn, indent=4, ensure_ascii=False)
        return data

    def prepare_subpage_folder(self, home_url):
        domain = urlparse(home_url).netloc
        slug_domain = slugify(domain)
        self.domain_path = os.path.join(self.subpages_path, slug_domain)
        makeDirIfNotExists(self.domain_path)
        return self.domain_path

    def read_pharmacy_data(self):
        with open(self.overview_file, 'r', encoding='utf-8') as fn:
            data = json.load(fn)
        return data

    def is_json_exists(self):
        return bool(os.path.exists(self.overview_file))

    def create_url_list_file(self, home_url):
        self.prepare_subpage_folder(home_url)
        url_list_path = os.path.join(self.domain_path, '0-url-list.json') # create json file to store all urls
        if not os.path.exists(url_list_path):
            initial = {
                "home_url": home_url,
                "sublinks": []
            }
            with open(url_list_path, 'w', encoding='utf-8') as fn:
                json.dump(initial, fn, indent=4, ensure_ascii=False)
        return url_list_path

    def prepare_file_path_for_subpage(self, subpage_url):
        parsed = urlparse(subpage_url)
        slug_domain = slugify(parsed.netloc)
        self.subpath = os.path.join(self.folder_path, 'subpages', slug_domain)
        makeDirIfNotExists(self.subpath)
        filename = f"{parsed.path}-{parsed.params}-{parsed.query}-{parsed.fragment}"
        if len(filename) > 100: # handle OS error filename too long
            filename = filename[:100]
        slug_subpage_filename = slugify(filename)
        if parsed.path == "/": # handle root of homepage
            slug_subpage_filename = '1-home'
        return os.path.join(self.subpath, slug_subpage_filename + ".json")
