// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { buildI18n, mount } from '@/tests/helpers/mount';
import en from '@/i18n/lng/en.js';
import es from '@/i18n/lng/es.js';
import Showcase from '@/components/landing/showcase.vue';

// Fixtures
const FEATURE_IDS = ['intentionGraph', 'bucket', 'extraction', 'batch', 'projects', 'language', 'usage'];
const RAW_KEY = /\b(?:admin|chat|landing|project)\.[A-Za-z]/;
const BATCH_RESULT = { en: /(\d+) created, (\d+) failed/, es: /(\d+) creadas, (\d+) fallida/ };

const mountIn = (locale) => {
  const i18n = buildI18n();
  i18n.global.locale.value = locale;
  return mount(Showcase, { global: { i18n } });
};

describe('Showcase.structure', () => {
  it('is the #features section and reuses the landing section title styling', () => {
    const wrapper = mount(Showcase);
    const section = wrapper.find('section');

    expect(section.attributes('id')).toBe('features');
    expect(section.classes()).toContain('orb-features');
    expect(wrapper.find('.orb-features-title').text()).toBe(en.landing.features.title);
    expect(wrapper.find('.orb-features-subtitle').text()).toBe(en.landing.features.subtitle);
  });

  it('splits the seven features into a daily-work group of five and a teams group of two', () => {
    const wrapper = mount(Showcase);
    const groups = wrapper.findAll('.orb-showcase-group');

    expect(groups.map((group) => group.find('.orb-showcase-group-label').text())).toEqual([
      en.landing.features.groups.work,
      en.landing.features.groups.team,
    ]);
    expect(groups.map((group) => group.findAll('.orb-showcase-row').length)).toEqual([5, 2]);
  });

  it('renders each feature with its own eyebrow, headline, pitch and proof points, in order', () => {
    const wrapper = mount(Showcase);
    const rows = wrapper.findAll('.orb-showcase-row');

    expect(rows).toHaveLength(FEATURE_IDS.length);
    rows.forEach((row, index) => {
      const copy = en.landing.features[FEATURE_IDS[index]];
      expect(row.find('.orb-showcase-eyebrow').text()).toBe(copy.eyebrow);
      expect(row.find('.orb-showcase-title').text()).toBe(copy.title);
      expect(row.find('.orb-showcase-desc').text()).toBe(copy.desc);
      expect(row.findAll('.orb-showcase-point').map((point) => point.text())).toEqual(Object.values(copy.points));
    });
  });

  it('alternates the text/mockup side within each group', () => {
    const wrapper = mount(Showcase);
    const reversed = wrapper.findAll('.orb-showcase-row').map((row) => row.classes().includes('orb-showcase-row--reverse'));

    // Work group (5 rows) then team group (2 rows); the index restarts per group.
    expect(reversed).toEqual([false, true, false, true, false, false, true]);
  });
});

describe('Showcase.mockups', () => {
  it('gives every feature exactly one decorative mockup hidden from assistive tech', () => {
    const wrapper = mount(Showcase);

    wrapper.findAll('.orb-showcase-row').forEach((row) => {
      const visual = row.find('.orb-showcase-visual');
      expect(visual.attributes('aria-hidden')).toBe('true');
      expect(visual.findAll('.orb-mock')).toHaveLength(1);
    });
  });

  it('draws the Intention Graph as completed, paused and nested active nodes using the real status labels', () => {
    const wrapper = mount(Showcase);
    const nodes = wrapper.findAll('.orb-mock-node');

    expect(nodes.map((node) => node.find('.orb-mock-pill').text())).toEqual([
      en.chat.intentionGraph.status.completed,
      en.chat.intentionGraph.status.paused,
      en.chat.intentionGraph.status.active,
    ]);
    expect(nodes[2].classes()).toContain('orb-mock-node--depth-1');
    expect(wrapper.find('.orb-mock-hint').text()).toContain(en.landing.features.intentionGraph.mock.resume);
  });

  it('shows a user upload and an assistant-generated file with the real bucket labels', () => {
    const wrapper = mount(Showcase);
    const files = wrapper.findAll('.orb-mock-file');

    expect(files.map((file) => file.find('.orb-mock-file-origin').text())).toEqual([
      en.chat.bucket.originUser,
      en.chat.bucket.originWorkflow,
    ]);
    expect(files[0].find('.orb-mock-chip').text()).toBe(en.chat.bucket.useAsContext);
  });

  it.each([['en', en], ['es', es]])('lists the invoice the hero chat delivers as the generated file, in %s', (locale, messages) => {
    const names = mountIn(locale).findAll('.orb-mock-file-name').map((name) => name.text());

    expect(names).toEqual(['orders_q3.csv', messages.landing.chat.step4.file]);
  });

  it('shows extracted key/value pairs and the form they fill', () => {
    const wrapper = mount(Showcase);
    const mock = en.landing.features.extraction.mock;

    expect(wrapper.findAll('.orb-mock-kv-label').map((label) => label.text())).toEqual([mock.supplier, mock.date, mock.qty]);
    expect(wrapper.findAll('.orb-mock-kv-value').map((value) => value.text())).toEqual([mock.supplierVal, mock.dateVal, mock.qtyVal]);
    expect(wrapper.find('.orb-mock-used').text()).toContain(mock.used);
  });

  it('shows a batch with created and failed records and a summary line', () => {
    const wrapper = mount(Showcase);
    const rows = wrapper.findAll('.orb-mock-row');

    expect(rows.map((row) => row.classes())).toEqual([
      expect.arrayContaining(['orb-mock-row--created']),
      expect.arrayContaining(['orb-mock-row--created']),
      expect.arrayContaining(['orb-mock-row--failed']),
    ]);
    expect(rows[0].text()).toContain('V10000');
    expect(rows[2].text()).toContain(en.landing.features.batch.mock.failed);
    expect(wrapper.find('.orb-mock-summary').text()).toBe(en.landing.features.batch.mock.summary);
  });

  it.each(['en', 'es'])('reports the same created/failed counts in the %s pitch, the summary and the rows', (locale) => {
    const wrapper = mountIn(locale);
    const pattern = BATCH_RESULT[locale];
    const [, created, failed] = wrapper.find('.orb-mock-summary').text().match(pattern);
    const [, pitchCreated, pitchFailed] = wrapper.findAll('.orb-showcase-desc')[FEATURE_IDS.indexOf('batch')].text().match(pattern);

    expect([pitchCreated, pitchFailed]).toEqual([created, failed]);
    expect(wrapper.findAll('.orb-mock-row--created')).toHaveLength(Number(created));
    expect(wrapper.findAll('.orb-mock-row--failed')).toHaveLength(Number(failed));
  });

  it('shows three projects with their chat counts, the first being the Default one', () => {
    const wrapper = mount(Showcase);
    const projects = wrapper.findAll('.orb-mock-project');

    expect(projects.map((project) => project.find('.orb-mock-project-name').text())).toEqual([
      en.project.default,
      en.landing.features.projects.mock.q4,
      en.landing.features.projects.mock.close,
    ]);
    expect(projects.map((project) => project.find('.orb-mock-project-count').text())).toEqual(['12 chats', '5 chats', '3 chats']);
  });

  it('shows the same exchange in English and in Spanish, in both locales', () => {
    ['en', 'es'].forEach((locale) => {
      const convos = mountIn(locale).findAll('.orb-mock-convo');

      expect(convos.map((convo) => convo.find('.orb-mock-lang-code').text())).toEqual(['EN', 'ES']);
      expect(convos[0].find('.orb-mock-bubble--agent').text()).toBe('You have 3 open purchase requests.');
      expect(convos[1].find('.orb-mock-bubble--agent').text()).toBe('Tienes 3 solicitudes de compra abiertas.');
    });
  });

  it('shows usage totals, ranked processes and seat usage with bar widths matching their share', () => {
    const wrapper = mount(Showcase);

    expect(wrapper.findAll('.orb-mock-stat-label').map((label) => label.text())).toEqual([
      en.admin.usage.totalProcesses,
      en.admin.usage.totalTokens,
    ]);
    expect(wrapper.findAll('.orb-mock-rank')).toHaveLength(4);
    expect(wrapper.findAll('.orb-mock-bar-fill').map((fill) => fill.attributes('style'))).toEqual([
      expect.stringContaining('width: 92%'),
      expect.stringContaining('width: 64%'),
      expect.stringContaining('width: 38%'),
      expect.stringContaining('width: 72%'),
    ]);
    expect(wrapper.findAll('.orb-mock-rank-head')[3].text()).toContain(en.admin.plan.seats);
  });
});

describe('Showcase.localization', () => {
  it.each(['en', 'es'])('renders every string from the %s messages, with no raw i18n key left on screen', (locale) => {
    const text = mountIn(locale).text();

    expect(text).not.toMatch(RAW_KEY);
  });

  it('renders the Spanish copy when the locale is es', () => {
    const wrapper = mountIn('es');
    const rows = wrapper.findAll('.orb-showcase-row');

    expect(wrapper.find('.orb-features-title').text()).toBe(es.landing.features.title);
    expect(rows.map((row) => row.find('.orb-showcase-title').text())).toEqual(
      FEATURE_IDS.map((id) => es.landing.features[id].title),
    );
    expect(wrapper.findAll('.orb-showcase-group-label').map((label) => label.text())).toEqual([
      es.landing.features.groups.work,
      es.landing.features.groups.team,
    ]);
  });
});
