<script setup>

  // Lib imports
  import { h, ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { v4 } from 'uuid';
  import dayjs from 'dayjs';

  // antd imports
  import { Button, message, Popconfirm } from 'antdv-next';
  import {
    DeleteOutlined,
    EditOutlined,
    SearchOutlined
  } from '@antdv-next/icons';

  // Components imports
  import mysearch from '@/components/table/search.vue'

  // Style imports
  import './list.css';

  const { actions, columns, loader } = defineProps({
    actions: {
      default: undefined,
      type: Object,
    },
    columns: {
      default: () => ([]),
      type: Array,
    },
    loader: {
      default: () => ({}),
      type: Function,
    },
    loading: {
      default: false,
      type: Boolean,
    }
  });
  const { t } = useI18n({ useScope: 'global' });
  const data = ref([]);
  const key = ref(v4());
  const loadingData = ref(true);
  const localColumns = ref(columns.map((column) => {
    if (!column.filterDropdown) return column;
    // filterDropdown here is only ever a truthy flag meaning "use the custom search
    // UI" — antdv-next's Table takes a real render function for this (no slot, no
    // separate customFilterDropdown flag), so it's replaced with one directly.
    // FilterDropdownProps doesn't include `column`, so it's closed over here.
    const { filterDropdown: _flag, ...rest } = column;
    return {
      ...rest,
      filterDropdown: (props) => h(mysearch, { ...props, column: rest }),
      filterIcon: (filtered) => h(SearchOutlined, { class: filtered ? 'filtered' : '' }),
    };
  }));
  const pagination = ref({
    current: 1,
    pageSize: 20,
  });

  const onChange = async (page = {}, filters = {}, sorter = {}) => {
    // on change table
    loadingData.value = true;

    // translate filters
    filters = Object.keys(filters).reduce((translated, key) => {
      let filterKeys = key;
      let filterValues = filters[key];
      if (filterValues !== null) {
        const column = columns.find((item) => item.dataIndex === key);
        let filterTypes = column.filterType || 'icontains';
        if (['datetime', 'number'].includes(column.type)) {
          if (column.type === 'datetime' ) {
            filterValues = filterValues[0].map(
              (value) => dayjs(value).format('YYYY-MM-DD')
            );
          }
          filterTypes = ['gte', 'lte'];
          filterKeys = [
            filterValues[0] && `${key}__${filterTypes[0]}`,
            filterValues[1] && `${key}__${filterTypes[1]}`,
          ];
        } else if (column.type === 'options') {
          filterKeys = [filterValues.length > 1 ? `${key}__in` : key];
          filterValues = [filterValues];
        } else {
          filterKeys = [`${key}__${filterTypes}`];
          filterValues = [filterValues];
        }
        filterKeys.forEach((filterKey, index) => {
          translated[filterKey] = filterValues[index];
        });
      }
      return translated;
    }, {});

    // Loader call
    const res = await loader({
      filters,
      sorter,
      limit: page.pageSize,
      offset: (page.current - 1) * page.pageSize,
    });
    if (res.errors) {
      res.errors.forEach((error) => {
        const code = error?.detail.replace(/ /g, '_').replace(/\./g, '').toUpperCase();
        message.error(t(`api.error.response.${error?.attr}.${code}`));
      });
      loadingData.value = false;
      return;
    }

    data.value = res.results;
    pagination.value = {
      ...pagination.value,
      current: page.current,
      pageSize: page.pageSize,
      total: res.count,
    };
    loadingData.value = false;
  }

  const remove = async (id) => {
    loadingData.value = true;
    const res = await actions.remover(id);
    if (res.errors) {
      res.errors.forEach((error) => {
        const code = error?.detail.replace(/ /g, '_').replace(/\./g, '').toUpperCase();
        message.error(t(`api.error.response.${error?.attr}.${code}`));
      });
      loadingData.value = false;
      return;
    }
    await onChange(pagination.value, {}, {});
    key.value = v4();
  }

  // add action to columns if needed
  const hasActions = columns.find((column) => column.key === 'actions');
  if (actions && !hasActions) {
    localColumns.value.push({
      key: 'actions',
      title: t(`commons.list.columns.actions`),
      render: (_, record) => {
        const nodes = [];
        if (actions.editor) {
          nodes.push(h(
            Button,
            {
              size: 'small',
              type: 'link',
              onClick: async () => await actions.editor(record),
            },
            { default: () => h(EditOutlined) }
          ));
        }
        if (actions.remover) {
          nodes.push(h(
            Popconfirm,
            {
              title: t('commons.list.actions.delete.confirm'),
              onConfirm: async () => await remove(record.id),
            },
            {
              default: () => h(
                Button,
                { size: 'small', type: 'link'},
                () => h(DeleteOutlined),
              ),
            },
          ));
        }
        return h('div', nodes);
      },
    });
  }

  onChange(pagination.value);

  defineExpose({
    refresh: () => onChange(pagination.value, {}, {}),
  });
</script>
<template>
  <div class="list">
    <a-table
      :key="key"
      :columns="localColumns"
      :dataSource="data"
      :loading="loading || loadingData"
      :pagination="pagination"
      :rowKey="(record) => record.id"
      :sortDirections="['ascend', 'descend', 'ascend']"
      @change="onChange"
    />
  </div>
</template>
