import abc
import operator
import typing
from abc import ABC
from functools import partial, reduce
from typing import Generic, TypeVar, Self, Callable, Iterable

T = TypeVar("T")
V = TypeVar("V")


class Functor(ABC, Generic[T]):

    @abc.abstractmethod
    def fmap(self, f: Callable[[T], V]) -> Self:
        ...

    def __matmul__(self, f):
        return self.fmap(f)


class Applicative(Functor[T], ABC):

    @classmethod
    @abc.abstractmethod
    def pure(cls, x: T) -> "Applicative[T]":
        ...

    @abc.abstractmethod
    def apply(self, p):
        ...

    def __mul__(self, f):
        return self.apply(f)

    @classmethod
    def sequence(cls, apps: Iterable[Self]) -> Self:
        def combine(p1: Self, p2: Self) -> Self:
            return (p1 @ (lambda l: lambda y: l + (y,))) * p2

        return reduce(combine, apps, cls.pure(tuple()))

    @classmethod
    def many(cls, parser):
        def many_v(s: str):
            return (
                liftA2(lambda x: lambda xs: [x] + xs, parser, many_v)
                .or_(cls.pure([]))
            )(s)

        return Parser(many_v)

    @classmethod
    def some(cls, parser):
        return liftA2(lambda x: lambda xs: [x] + xs, parser, cls.many(parser))

    def __lt__(self, other) -> Self:
        return liftA2(lambda a: lambda b: a, self, other)

    def __gt__(self, other) -> Self:
        return liftA2(lambda a: lambda b: b, self, other)


class Alternative(Applicative[T]):

    @abc.abstractmethod
    def or_(self, other: Self) -> Self:
        ...

    def __or__(self, other):
        return self.or_(other)


class Parser(Alternative[T]):

    def __init__(self, parse: Callable[[str], tuple[str, T] | None]):
        self._parse = parse

    def __call__(self, s: str):
        return self._parse(s)

    def fmap(self, f: Callable[[T], V]) -> "Parser[V]":
        def parse(s: str):
            if parsed := self._parse(s):
                left, res = parsed
                return left, f(res)
            return None

        return Parser(parse)

    @classmethod
    def pure(cls, x: T) -> Self:
        def parse(s: str):
            return s, x

        return Parser(parse)

    def apply(self, p):
        def parse(s: str):
            if res := self(s):
                left, func = res
                if res := p(left):
                    left, res = res
                    return left, func(res)

        return Parser(parse)

    def or_(self, other: "Parser[T]") -> "Parser[T]":
        def parse(s: str):
            return self(s) or other(s)

        return Parser(parse)


def match(p) -> Parser[str]:
    def parser(s: str):
        if s and p(s[0]):
            return s[1:], s[0]
        return None

    return Parser(parser)


def match_char(c: str) -> Parser:
    return match(partial(operator.eq, c))


def choice(*parsers: Alternative[T]) -> Alternative[T]:
    return reduce(operator.or_, parsers)


def match_str(s: str) -> Parser[str]:
    return Parser.sequence(map(match_char, s)) @ "".join


def liftA2(f, p1, p2):
    return p1 @ f * p2


def sep_by(parser: Parser[T], sep: Parser) -> Parser[list[T]]:
    return liftA2(
        lambda x: lambda xs: [x] + xs,
        parser,
        Parser.many(sep > parser)
    ).or_(Parser.pure([]))


def white_spaces() -> Parser:
    return Parser.many(match(lambda c: c.isspace))


def wrap(p: Parser, l: Parser, r: Parser) -> Parser:
    return l > p < r


#
# #
# # def json_parser(s: str) -> Parsed:
# #     return choice(
# #         # null
# #         fmap(lambda x: None, match_str("null")),
# #         # bool
# #         fmap(
# #             lambda x: x == "true",
# #             or_(match_str("true"), match_str("false"))
# #         ),
# #         # number
# #         fmap(
# #             lambda l: int("".join(l)),
# #             some(match(lambda c: c.isnumeric()))
# #         ),
# #         # string
# #         string_literal(),
# #         # array
# #         wrap(
# #             sep_by(
# #                 json_parser,
# #                 match_char(","),
# #             ),
# #             match_char("["), match_char("]")
# #         ),
# #         # obj
# #         fmap(
# #             dict,
# #             wrap(
# #                 sep_by(
# #                     pairs(),
# #                     match_char(","),
# #                 ),
# #                 match_char("{"), match_char("}")
# #             )
# #         )
# #
# #     )(s)


def json_parser():
    def parser(s):
        null_parser = match_str("null") @ (lambda x: None)

        bool_parser = match_str("true").or_(match_str("false")) @ (lambda rslt: rslt == "true")

        num_parser = Parser.some(match(str.isnumeric)) @ "".join @ int

        str_parser = (match_char("\"") >
                      (Parser.many(match(lambda s: s != '"'))
                       < match_char("\""))) @ "".join

        arr_parser = (match_char('[') >
                      (sep_by(json_parser(), match_char(","))
                       # fix this??
                       < match_char("]")))

        pair = (Parser.sequence(
            [str_parser, match_char(":"), json_parser()])
                @ (lambda l: (l[0], l[2])))

        obj_parser = (match_char('{') >
                      (sep_by(pair, match_char(","))
                       # fix this??
                       < match_char("}"))) @ dict

        return choice(
            null_parser,
            bool_parser,
            num_parser,
            str_parser,
            arr_parser,
            obj_parser,
        )(s)

    return Parser(parser)


if __name__ == '__main__':
    r = json_parser()
    print(r('{"xxx":12,"bbb":[{"a":false},null]}'))
