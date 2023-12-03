# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html
import scrapy

from itemloaders.processors import TakeFirst, MapCompose, Join
from w3lib.html import remove_tags


def remove_symbols(value: str) -> str:
    symbols = ['\xa0', '€', '$']
    for symbol in symbols:
        value = value.replace(symbol, '')
    return value.replace(',', '.')


def remove_n(value: str) -> str:
    value = value.replace('\n', '').strip()
    return ' '.join([i for i in value.split(' ') if i])


def remove_strs(value: str) -> str:
    return ''.join([i for i in value if i.isdigit()])


class Product(scrapy.Item):
    link = scrapy.Field(
        input_processor=MapCompose(),
        output_processor=TakeFirst(),
    )
    ean = scrapy.Field(
        input_processor=MapCompose(remove_tags, float, int, str),
        output_processor=TakeFirst(),
    )
    title = scrapy.Field(
        input_processor=MapCompose(remove_tags, remove_n),
        output_processor=TakeFirst(),
    )
    price = scrapy.Field(
        input_processor=MapCompose(remove_tags, remove_n, remove_symbols),
        output_processor=TakeFirst()
    )
    description = scrapy.Field(
        input_processor=MapCompose(remove_tags, remove_n),
        output_processor=TakeFirst()
    )
    breadcrumb = scrapy.Field(
        input_processor=MapCompose(remove_tags, remove_n),
        output_processor=Join(separator=' > ')
    )
    review_rate = scrapy.Field(
        input_processor=MapCompose(remove_tags, float, str),
        output_processor=TakeFirst()
    )
    review_nb = scrapy.Field(
        input_processor=MapCompose(remove_tags, float, int, str),
        output_processor=TakeFirst()
    )
    screenshot = scrapy.Field(
        input_processor=MapCompose(),
        output_processor=TakeFirst()
    )
