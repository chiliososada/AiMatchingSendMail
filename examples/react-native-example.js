// examples/react-native-example.js
// React Native 邮件API使用示例

import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  Alert,
  ScrollView,
  StyleSheet,
  Platform,
  ActivityIndicator,
  FlatList
} from 'react-native';
import DocumentPicker from 'react-native-document-picker';
import RNFS from 'react-native-fs';

// 邮件API服务类
class EmailAPIService {
  constructor(baseURL = 'http://your-server:8000/api/v1/email') {
    this.baseURL = baseURL;
    this.tenantId = 'your-tenant-id'; // 实际使用时应该动态获取
  }

  // 创建SMTP配置
  async createSMTPSettings(smtpConfig) {
    try {
      const response = await fetch(`${this.baseURL}/smtp-settings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tenant_id: this.tenantId,
          ...smtpConfig
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('创建SMTP设置失败:', error);
      throw error;
    }
  }

  // 获取SMTP设置列表
  async getSMTPSettings() {
    try {
      const response = await fetch(`${this.baseURL}/smtp-settings/${this.tenantId}`);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('获取SMTP设置失败:', error);
      throw error;
    }
  }

  // 测试SMTP连接
  async testSMTPConnection(smtpSettingId, testEmail) {
    try {
      const response = await fetch(`${this.baseURL}/smtp-settings/test`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tenant_id: this.tenantId,
          smtp_setting_id: smtpSettingId,
          test_email: testEmail
        })
      });

      return await response.json();
    } catch (error) {
      console.error('SMTP连接测试失败:', error);
      throw error;
    }
  }

  // 上传附件
  async uploadAttachment(fileUri, fileName, fileType) {
    try {
      const formData = new FormData();
      formData.append('tenant_id', this.tenantId);
      formData.append('file', {
        uri: fileUri,
        type: fileType,
        name: fileName
      });

      const response = await fetch(`${this.baseURL}/attachments/upload`, {
        method: 'POST',
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        body: formData
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('上传附件失败:', error);
      throw error;
    }
  }

  // 发送普通邮件
  async sendEmail(emailData) {
    try {
      const response = await fetch(`${this.baseURL}/send`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tenant_id: this.tenantId,
          ...emailData
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('发送邮件失败:', error);
      throw error;
    }
  }

  // 发送带附件的邮件
  async sendEmailWithAttachments(emailData) {
    try {
      const response = await fetch(`${this.baseURL}/send-with-attachments`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tenant_id: this.tenantId,
          ...emailData
        })
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('发送带附件邮件失败:', error);
      throw error;
    }
  }

  // 获取邮件状态
  async getEmailStatus(queueId) {
    try {
      const response = await fetch(`${this.baseURL}/queue/${this.tenantId}/${queueId}`);

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('获取邮件状态失败:', error);
      throw error;
    }
  }

  // 获取邮件队列列表
  async getEmailQueue(limit = 20, offset = 0) {
    try {
      const response = await fetch(
        `${this.baseURL}/queue/${this.tenantId}?limit=${limit}&offset=${offset}`
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('获取邮件队列失败:', error);
      throw error;
    }
  }

  // 获取发送统计
  async getEmailStatistics(days = 30) {
    try {
      const response = await fetch(
        `${this.baseURL}/statistics/${this.tenantId}?days=${days}`
      );

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('获取邮件统计失败:', error);
      throw error;
    }
  }
}

// React Native 组件示例
const EmailApp = () => {
  const [emailService] = useState(new EmailAPIService());
  const [loading, setLoading] = useState(false);

  // SMTP配置状态
  const [smtpSettings, setSMTPSettings] = useState([]);
  const [showSMTPForm, setShowSMTPForm] = useState(false);

  // 邮件发送状态
  const [emailForm, setEmailForm] = useState({
    to_emails: '',
    subject: '',
    body_text: '',
    body_html: ''
  });

  // 附件状态
  const [attachments, setAttachments] = useState([]);
  const [uploadingFile, setUploadingFile] = useState(false);

  // 邮件队列状态
  const [emailQueue, setEmailQueue] = useState([]);
  const [statistics, setStatistics] = useState(null);

  // 组件挂载时加载数据
  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    try {
      setLoading(true);
      await Promise.all([
        loadSMTPSettings(),
        loadEmailQueue(),
        loadStatistics()
      ]);
    } catch (error) {
      Alert.alert('错误', '加载数据失败');
    } finally {
      setLoading(false);
    }
  };

  // 加载SMTP设置
  const loadSMTPSettings = async () => {
    try {
      const settings = await emailService.getSMTPSettings();
      setSMTPSettings(settings);
    } catch (error) {
      console.error('加载SMTP设置失败:', error);
    }
  };

  // 加载邮件队列
  const loadEmailQueue = async () => {
    try {
      const queue = await emailService.getEmailQueue();
      setEmailQueue(queue);
    } catch (error) {
      console.error('加载邮件队列失败:', error);
    }
  };

  // 加载统计数据
  const loadStatistics = async () => {
    try {
      const stats = await emailService.getEmailStatistics();
      setStatistics(stats);
    } catch (error) {
      console.error('加载统计数据失败:', error);
    }
  };

  // 创建SMTP配置
  const createSMTPSettings = async (config) => {
    try {
      setLoading(true);
      await emailService.createSMTPSettings(config);
      Alert.alert('成功', 'SMTP配置创建成功');
      await loadSMTPSettings();
      setShowSMTPForm(false);
    } catch (error) {
      Alert.alert('错误', '创建SMTP配置失败');
    } finally {
      setLoading(false);
    }
  };

  // 选择文件
  const pickDocument = async () => {
    try {
      const result = await DocumentPicker.pick({
        type: [DocumentPicker.types.allFiles],
        allowMultiSelection: true
      });

      for (const file of result) {
        await uploadFile(file);
      }
    } catch (error) {
      if (DocumentPicker.isCancel(error)) {
        console.log('用户取消了文件选择');
      } else {
        Alert.alert('错误', '选择文件失败');
      }
    }
  };

  // 上传文件
  const uploadFile = async (file) => {
    try {
      setUploadingFile(true);

      const result = await emailService.uploadAttachment(
        file.uri,
        file.name,
        file.type
      );

      setAttachments(prev => [...prev, {
        id: result.attachment_id,
        name: result.filename,
        size: result.file_size,
        type: result.content_type
      }]);

      Alert.alert('成功', `文件 ${file.name} 上传成功`);
    } catch (error) {
      Alert.alert('错误', `上传文件失败: ${error.message}`);
    } finally {
      setUploadingFile(false);
    }
  };

  // 发送邮件
  const sendEmail = async () => {
    try {
      // 验证表单
      if (!emailForm.to_emails.trim()) {
        Alert.alert('错误', '请输入收件人邮箱');
        return;
      }

      if (!emailForm.subject.trim()) {
        Alert.alert('错误', '请输入邮件主题');
        return;
      }

      setLoading(true);

      const emailData = {
        to_emails: emailForm.to_emails.split(',').map(email => email.trim()),
        subject: emailForm.subject,
        body_text: emailForm.body_text,
        body_html: emailForm.body_html || `<p>${emailForm.body_text}</p>`
      };

      let result;

      if (attachments.length > 0) {
        // 发送带附件的邮件
        emailData.attachment_ids = attachments.map(att => att.id);
        result = await emailService.sendEmailWithAttachments(emailData);
      } else {
        // 发送普通邮件
        result = await emailService.sendEmail(emailData);
      }

      Alert.alert('成功', '邮件发送成功', [
        {
          text: '确定',
          onPress: () => {
            // 清空表单
            setEmailForm({
              to_emails: '',
              subject: '',
              body_text: '',
              body_html: ''
            });
            setAttachments([]);
            // 刷新邮件队列
            loadEmailQueue();
          }
        }
      ]);

    } catch (error) {
      Alert.alert('错误', `发送邮件失败: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // 测试SMTP连接
  const testSMTPConnection = async (settingId) => {
    try {
      setLoading(true);
      const result = await emailService.testSMTPConnection(
        settingId,
        'test@example.com'
      );

      if (result.status === 'success') {
        Alert.alert('成功', 'SMTP连接测试成功');
      } else {
        Alert.alert('失败', `SMTP连接测试失败: ${result.message}`);
      }
    } catch (error) {
      Alert.alert('错误', `连接测试失败: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // 格式化文件大小
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  // 渲染SMTP设置项
  const renderSMTPSetting = ({ item }) => (
    <View style={styles.settingItem}>
      <Text style={styles.settingName}>{item.setting_name}</Text>
      <Text style={styles.settingEmail}>{item.from_email}</Text>
      <View style={styles.settingActions}>
        <TouchableOpacity
          style={[styles.button, styles.testButton]}
          onPress={() => testSMTPConnection(item.id)}
        >
          <Text style={styles.buttonText}>测试连接</Text>
        </TouchableOpacity>
      </View>
    </View>
  );

  // 渲染附件项
  const renderAttachment = ({ item }) => (
    <View style={styles.attachmentItem}>
      <Text style={styles.attachmentName}>{item.name}</Text>
      <Text style={styles.attachmentSize}>{formatFileSize(item.size)}</Text>
      <TouchableOpacity
        style={styles.removeButton}
        onPress={() => setAttachments(prev => prev.filter(att => att.id !== item.id))}
      >
        <Text style={styles.removeButtonText}>×</Text>
      </TouchableOpacity>
    </View>
  );

  // 渲染邮件队列项
  const renderQueueItem = ({ item }) => (
    <View style={styles.queueItem}>
      <Text style={styles.queueSubject}>{item.subject}</Text>
      <Text style={styles.queueEmails}>
        收件人: {Array.isArray(item.to_emails) ? item.to_emails.join(', ') : item.to_emails}
      </Text>
      <Text style={styles.queueStatus}>状态: {item.status}</Text>
      <Text style={styles.queueTime}>
        创建时间: {new Date(item.created_at).toLocaleString()}
      </Text>
    </View>
  );

  if (loading && !emailQueue.length && !smtpSettings.length) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.loadingText}>加载中...</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      {/* 统计信息 */}
      {statistics && (
        <View style={styles.statisticsContainer}>
          <Text style={styles.sectionTitle}>发送统计</Text>
          <View style={styles.statsRow}>
            <View style={styles.statItem}>
              <Text style={styles.statNumber}>{statistics.total_sent}</Text>
              <Text style={styles.statLabel}>已发送</Text>
            </View>
            <View style={styles.statItem}>
              <Text style={styles.statNumber}>{statistics.total_failed}</Text>
              <Text style={styles.statLabel}>失败</Text>
            </View>
            <View style={styles.statItem}>
              <Text style={styles.statNumber}>{statistics.success_rate}%</Text>
              <Text style={styles.statLabel}>成功率</Text>
            </View>
          </View>
        </View>
      )}

      {/* SMTP设置 */}
      <View style={styles.section}>
        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>SMTP设置</Text>
          <TouchableOpacity
            style={styles.addButton}
            onPress={() => setShowSMTPForm(!showSMTPForm)}
          >
            <Text style={styles.addButtonText}>+</Text>
          </TouchableOpacity>
        </View>

        <FlatList
          data={smtpSettings}
          renderItem={renderSMTPSetting}
          keyExtractor={item => item.id}
          scrollEnabled={false}
        />
      </View>

      {/* 邮件发送表单 */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>发送邮件</Text>

        <TextInput
          style={styles.input}
          placeholder="收件人邮箱 (多个邮箱用逗号分隔)"
          value={emailForm.to_emails}
          onChangeText={(text) => setEmailForm(prev => ({ ...prev, to_emails: text }))}
          keyboardType="email-address"
        />

        <TextInput
          style={styles.input}
          placeholder="邮件主题"
          value={emailForm.subject}
          onChangeText={(text) => setEmailForm(prev => ({ ...prev, subject: text }))}
        />

        <TextInput
          style={[styles.input, styles.textArea]}
          placeholder="邮件内容"
          value={emailForm.body_text}
          onChangeText={(text) => setEmailForm(prev => ({ ...prev, body_text: text }))}
          multiline
          numberOfLines={4}
        />

        {/* 附件列表 */}
        {attachments.length > 0 && (
          <View style={styles.attachmentsContainer}>
            <Text style={styles.attachmentsTitle}>附件 ({attachments.length})</Text>
            <FlatList
              data={attachments}
              renderItem={renderAttachment}
              keyExtractor={item => item.id}
              scrollEnabled={false}
            />
          </View>
        )}

        {/* 操作按钮 */}
        <View style={styles.actionButtons}>
          <TouchableOpacity
            style={[styles.button, styles.attachButton]}
            onPress={pickDocument}
            disabled={uploadingFile}
          >
            <Text style={styles.buttonText}>
              {uploadingFile ? '上传中...' : '添加附件'}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.button, styles.sendButton]}
            onPress={sendEmail}
            disabled={loading}
          >
            <Text style={styles.buttonText}>
              {loading ? '发送中...' : '发送邮件'}
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* 邮件队列 */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>邮件队列</Text>
        <FlatList
          data={emailQueue.slice(0, 10)} // 只显示最近10条
          renderItem={renderQueueItem}
          keyExtractor={item => item.id}
          scrollEnabled={false}
        />
      </View>
    </ScrollView>
  );
};

// 样式定义
const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
    padding: 16
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center'
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#666'
  },
  section: {
    backgroundColor: 'white',
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333'
  },
  statisticsContainer: {
    backgroundColor: 'white',
    borderRadius: 8,
    padding: 16,
    marginBottom: 16
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around'
  },
  statItem: {
    alignItems: 'center'
  },
  statNumber: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#007AFF'
  },
  statLabel: {
    fontSize: 12,
    color: '#666',
    marginTop: 4
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    marginBottom: 12,
    backgroundColor: '#fff'
  },
  textArea: {
    height: 100,
    textAlignVertical: 'top'
  },
  button: {
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
    marginVertical: 4
  },
  sendButton: {
    backgroundColor: '#007AFF',
    flex: 1,
    marginLeft: 8
  },
  attachButton: {
    backgroundColor: '#34C759',
    flex: 1,
    marginRight: 8
  },
  testButton: {
    backgroundColor: '#FF9500',
    paddingHorizontal: 16,
    paddingVertical: 8
  },
  addButton: {
    backgroundColor: '#007AFF',
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center'
  },
  addButtonText: {
    color: 'white',
    fontSize: 20,
    fontWeight: 'bold'
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600'
  },
  actionButtons: {
    flexDirection: 'row',
    marginTop: 16
  },
  settingItem: {
    borderWidth: 1,
    borderColor: '#eee',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8
  },
  settingName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333'
  },
  settingEmail: {
    fontSize: 14,
    color: '#666',
    marginTop: 4
  },
  settingActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    marginTop: 8
  },
  attachmentsContainer: {
    marginTop: 16,
    marginBottom: 8
  },
  attachmentsTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8
  },
  attachmentItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 8,
    backgroundColor: '#f8f9fa',
    borderRadius: 4,
    marginBottom: 4
  },
  attachmentName: {
    flex: 1,
    fontSize: 14,
    color: '#333'
  },
  attachmentSize: {
    fontSize: 12,
    color: '#666',
    marginRight: 8
  },
  removeButton: {
    backgroundColor: '#FF3B30',
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center'
  },
  removeButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: 'bold'
  },
  queueItem: {
    borderWidth: 1,
    borderColor: '#eee',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8
  },
  queueSubject: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333'
  },
  queueEmails: {
    fontSize: 14,
    color: '#666',
    marginTop: 4
  },
  queueStatus: {
    fontSize: 14,
    color: '#007AFF',
    marginTop: 4
  },
  queueTime: {
    fontSize: 12,
    color: '#999',
    marginTop: 4
  }
});

export default EmailApp;

// 使用示例：
// import EmailApp from './examples/react-native-example';
// 
// const App = () => {
//   return <EmailApp />;
// };
//
// export default App;