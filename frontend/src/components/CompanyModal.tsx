import React, { useState } from 'react';
import { Modal, Form, Input, message } from 'antd';
import { createCompany } from '../api';

interface Props {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const CompanyModal: React.FC<Props> = ({ open, onClose, onSuccess }) => {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  const handleOk = async () => {
    try {
      const values = await form.validateFields();
      setSubmitting(true);
      await createCompany(values);
      message.success('新增企业成功');
      form.resetFields();
      onSuccess();
    } catch (e: any) {
      if (e.errorFields) return; // 表单校验未通过
      message.error('新增失败: ' + (e.message || ''));
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = () => {
    form.resetFields();
    onClose();
  };

  return (
    <Modal
      title="新增企业"
      open={open}
      onOk={handleOk}
      onCancel={handleCancel}
      confirmLoading={submitting}
      destroyOnClose
    >
      <Form form={form} layout="vertical" autoComplete="off">
        <Form.Item
          name="name"
          label="企业名称"
          rules={[{ required: true, message: '请输入企业名称' }]}
        >
          <Input placeholder="请输入企业全称" maxLength={200} />
        </Form.Item>
        <Form.Item
          name="credit_code"
          label="统一社会信用代码"
          rules={[
            { required: true, message: '请输入统一社会信用代码' },
            { min: 18, max: 18, message: '统一社会信用代码为18位' },
          ]}
        >
          <Input placeholder="请输入18位统一社会信用代码" maxLength={18} />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default CompanyModal;
