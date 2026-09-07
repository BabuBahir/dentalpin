// Message-level fallback: a key missing from the active locale renders
// its English text instead of the raw dotted key. Module layers add
// their locale files independently of the host (#131, #144), so a
// language can ship core-first and the optional modules' UI degrades
// to English until their translations land — never to `some.dotted.key`
// on a clinician's screen (the drift #126 documents).
//
function plPluralRule(choice: number, choicesLength: number): number {
  if (choice === 1) return 0
  const teen = choice % 100 >= 12 && choice % 100 <= 14
  const few = choice % 10 >= 2 && choice % 10 <= 4 && !teen
  if (choicesLength === 2) return 1
  return few ? 1 : 2
}

// Arabic pluralization (vue-i18n `choice`): CLDR gives Arabic six
// categories. The rule maps a count to the index vue-i18n uses to pick
// the pipe segment: 0 → zero, 1 → one, 2 → two, 3-10 → few,
// 11-99 → many, everything else → other (index 5).
function arPluralRule(choice: number, choicesLength: number): number {
  const max = choicesLength - 1
  if (choicesLength === 2) return choice === 1 ? 0 : Math.min(1, max)
  const mod100 = Math.abs(choice) % 100
  if (choice === 0) return Math.min(0, max)
  if (choice === 1) return Math.min(1, max)
  if (choice === 2) return Math.min(2, max)
  if (mod100 >= 3 && mod100 <= 10) return Math.min(3, max)
  if (mod100 >= 11 && mod100 <= 99) return Math.min(4, max)
  return Math.min(5, max)
}

export default defineI18nConfig(() => ({
  fallbackLocale: 'en',
  missingWarn: false,
  fallbackWarn: false,
  pluralRules: { pl: plPluralRule, ar: arPluralRule },
  // Named date format used by the module detail modal (`d(value, 'short')`).
  // Registered for every shipped locale so no locale falls back with a
  // console warning (L18 parity applies to config-level formats too).
  datetimeFormats: {
    es: { short: { dateStyle: 'short', timeStyle: 'short' } },
    en: { short: { dateStyle: 'short', timeStyle: 'short' } },
    de: { short: { dateStyle: 'short', timeStyle: 'short' } },
    fr: { short: { dateStyle: 'short', timeStyle: 'short' } },
    hu: { short: { dateStyle: 'short', timeStyle: 'short' } },
    it: { short: { dateStyle: 'short', timeStyle: 'short' } },
    pl: { short: { dateStyle: 'short', timeStyle: 'short' } },
    pt: { short: { dateStyle: 'short', timeStyle: 'short' } },
    ta: { short: { dateStyle: 'short', timeStyle: 'short' } },
    ar: { short: { dateStyle: 'short', timeStyle: 'short' } }
  }
}))
