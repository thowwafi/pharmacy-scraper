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
        self.url_list_path = self.get_url_list_path()
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

    def get_url_list_path(self):
        path = os.path.join(self.folder_path, "url_list")
        makeDirIfNotExists(path)
        return path

    def get_subpages_path(self):
        subpage = os.path.join(self.folder_path, "subpages")
        makeDirIfNotExists(subpage)
        return subpage

    def get_overview_file(self):
        return os.path.join(self.overview_path, self.slug_name + ".json")

    def is_suggestions_exist(self):
        """
            Check if the current pharmacy already got suggestion links
            Return:
                - True or False
        """
        if not os.path.exists(self.overview_file):
            return False
        
        with open(self.overview_file, 'r', encoding='utf-8') as fn:
            data = json.load(fn)
        return bool(data.get('suggestions'))

    def get_suggestions(self):
        with open(self.overview_file, 'r', encoding='utf-8') as fn:
            data = json.load(fn)
        return data.get('suggestions')

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

    def read_pharmacy_data(self):
        with open(self.overview_file, 'r', encoding='utf-8') as fn:
            data = json.load(fn)
        return data

    def update_pharmacy_data(self, updated_pharmacy_data):
        with open(self.overview_file, 'w', encoding='utf-8') as fn:
            json.dump(updated_pharmacy_data, fn, indent=4, ensure_ascii=False)

    def get_subpage_home_url_path(self, home_url):
        parsed = urlparse(home_url)
        slug_domain = slugify(parsed.netloc)
        self.subpath_homepage = os.path.join(self.folder_path, 'subpages', slug_domain)
        makeDirIfNotExists(self.subpath_homepage)
        return self.subpath_homepage

    def prepare_file_path_for_subpage(self, subpage_url, count):
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

    def save_subpage_content(self, filepath, subpage_dict):
        with open(filepath, 'w', encoding='utf-8') as fn:
            json.dump(subpage_dict, fn, indent=4, ensure_ascii=False)

    def get_suggestion_output_path(self, home_url):
        os.path.join(self.subpages_path, 'hom')

        
    def create_url_list(self, home_url):
        filepath = os.path.join(self.url_list_path, self.slug_name + ".json")
        if not os.path.exists(filepath):
            with open(filepath, 'w', encoding='utf-8') as fn:
                json.dump([], fn, indent=4, ensure_ascii=False)
        return filepath

    def get_subpages_list(self, home_url):
        with open(self.overview_file, 'r', encoding='utf-8') as fn:
            data = json.load(fn)
        import pdb; pdb.set_trace()

    
        
