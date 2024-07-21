import operator
from functools import partial, reduce
from pprint import pprint
from typing import TypeVar, Callable, Iterable, Any

T = TypeVar("T")
V = TypeVar("V")
Predicate = Callable[[T], bool]
Parsed = tuple[str, T] | None
Parser = Callable[[str], Parsed]


def fmap(f: Callable[[T], V], p: Parser[T]) -> Parser[V]:
    def parser(s: str) -> Parsed:
        if parsed := p(s):
            left, res = parsed
            return left, f(res)
        return None

    return parser


def pure(x: T) -> Parser[T]:
    def parser(s: str) -> Parsed:
        return s, x

    return parser


def and_then(f: Parser[Callable[[T], V]], p: Parser[T]) -> Parser[V]:
    def parser(s: str) -> Parsed:
        if res := f(s):
            left, func = res
            if res := p(left):
                left, res = res
                return left, func(res)

    return parser


def or_(p1: Parser[T], p2: Parser[T]) -> Parser[T]:
    def parser(s: str) -> Parsed:
        return p1(s) or p2(s)

    return parser


def match(p: Predicate[str]) -> Parser[str]:
    def parser(s: str) -> Parsed:
        if s and p(s[0]):
            return s[1:], s[0]
        return None

    return parser


def match_char(c: str) -> Parser:
    return match(partial(operator.eq, c))


def sequence(parsers: Iterable[Parser[T]]) -> Parser[tuple[T]]:
    def combine(p1: Parser[tuple[T]], p2: Parser[T]) -> Parser[tuple[T]]:
        return and_then(
            fmap(lambda l: lambda y: l + (y,), p1),
            p2
        )

    return reduce(combine, parsers, pure(tuple()))


def choice(*parsers: Parser[T]) -> Parser[T]:
    return reduce(or_, parsers)


def match_str(s: str) -> Parser[str]:
    return fmap("".join, sequence(map(match_char, s)))


def liftA2(f, p1, p2):
    return and_then(fmap(f, p1), p2)


def many(parser):
    def many_v(s: str):
        return or_(
            liftA2(lambda x: lambda xs: [x] + xs, parser, many_v),
            pure([]))(s)

    return many_v


def some(parser):
    return liftA2(lambda x: lambda xs: [x] + xs, parser, many(parser))


# <
def then_left(a1, a2):
    return liftA2(lambda a: lambda b: a, a1, a2)


# >
def then_right(a1, a2):
    return liftA2(lambda a: lambda b: b, a1, a2)


def sep_by(parser: Parser[T], sep: Parser) -> Parser[list[T]]:
    return or_(
        liftA2(lambda x: lambda xs: [x] + xs, parser, many(then_right(sep, parser))),
        pure([])
    )


def white_spaces() -> Parser:
    return many(match(lambda c: c.isspace))


def wrap(p, l, r) -> Parser:
    return then_right(l, then_left(p, r))


def string_literal():
    return fmap(
        "".join,
        wrap(
            many(match(lambda s: s != '"')),
            l=match_char("\""),
            r=match_char("\""))
    )


def json_parser(s: str) -> Parsed:
    return choice(
        # null
        fmap(lambda x: None, match_str("null")),
        # bool
        fmap(
            lambda x: x == "true",
            or_(match_str("true"), match_str("false"))
        ),
        # number
        fmap(
            lambda l: int("".join(l)),
            some(match(lambda c: c.isnumeric()))
        ),
        # string
        string_literal(),
        # array
        wrap(
            sep_by(
                json_parser,
                match_char(","),
            ),
            match_char("["), match_char("]")
        ),
        # obj
        fmap(
            dict,
            wrap(
                sep_by(
                    pairs(),
                    match_char(","),
                ),
                match_char("{"), match_char("}")
            )
        )

    )(s)


def pairs() -> Parser[tuple[str, Any]]:
    s = sequence(
        [string_literal(), match_char(":"), json_parser]
    )
    return fmap(lambda l: (l[0], l[2]), s)


if __name__ == '__main__':
    r = fmap(ord, match_char("c"))("clalal")
    # r = json_parser("\"asdfgh\"")
    # r = json_parser("[\"asdfgh\",123]")
    _, r = json_parser('{"str":1234,"x":{"basd":[123,5432,null]}}')
    pprint(r)
